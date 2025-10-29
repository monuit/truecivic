import datetime

from lxml import etree
import requests

from django.db import transaction
from django.utils import timezone

from parliament.bills.models import Bill, VoteQuestion, MemberVote
from parliament.core.models import ElectedMember, Politician, Session
from parliament.orchestration.watermarks import get_watermark, update_watermark

import logging
logger = logging.getLogger(__name__)

VOTELIST_URL = 'https://www.ourcommons.ca/members/{lang}/votes/xml'
VOTEDETAIL_URL = 'https://www.ourcommons.ca/members/en/votes/{parliamentnum}/{sessnum}/{votenumber}/xml'

@transaction.atomic
def import_votes():
    watermark = get_watermark("votes")
    watermark_meta = dict(watermark.metadata or {})
    latest_timestamp = watermark.timestamp
    latest_token = watermark.token
    latest_meta = dict(watermark_meta)

    votelisturl_en = VOTELIST_URL.format(lang='en')
    resp = requests.get(votelisturl_en)
    resp.raise_for_status()
    root = etree.fromstring(resp.content)

    votelisturl_fr = VOTELIST_URL.format(lang='fr')
    resp = requests.get(votelisturl_fr)
    resp.raise_for_status()
    root_fr = etree.fromstring(resp.content)
    votelist = root.findall('Vote')
    for vote in votelist:
        votenumber = int(vote.findtext('DecisionDivisionNumber'))
        session = Session.objects.get(
            parliamentnum=int(vote.findtext('ParliamentNumber')),
            sessnum=int(vote.findtext('SessionNumber'))
        )

        token_meta = {
            'parliament': session.parliamentnum,
            'session': session.sessnum,
            'vote': votenumber,
        }
        token = f"{token_meta['parliament']}:{token_meta['session']}:{votenumber}"

        event_dt = datetime.datetime.strptime(
            vote.findtext('DecisionEventDateTime'), '%Y-%m-%dT%H:%M:%S'
        )
        if timezone.is_naive(event_dt):
            event_dt = timezone.make_aware(event_dt, timezone=timezone.utc)
        vote_date = event_dt.date()

        skip_due_to_watermark = False
        if watermark.timestamp:
            if event_dt < watermark.timestamp:
                skip_due_to_watermark = True
            elif event_dt == watermark.timestamp:
                same_parl = (
                    token_meta['parliament'] == watermark_meta.get('parliament')
                )
                same_session = (
                    token_meta['session'] == watermark_meta.get('session')
                )
                last_number = watermark_meta.get('vote')
                if (
                    same_parl
                    and same_session
                    and isinstance(last_number, int)
                    and token_meta['vote'] <= last_number
                ):
                    skip_due_to_watermark = True

        existing = VoteQuestion.objects.filter(
            session=session, number=votenumber
        ).exists()
        if skip_due_to_watermark and existing:
            continue
        if existing:
            if (
                latest_timestamp is None
                or event_dt > latest_timestamp
                or (
                    event_dt == latest_timestamp
                    and token_meta['vote'] > latest_meta.get('vote', -1)
                )
            ):
                latest_timestamp = event_dt
                latest_token = token
                latest_meta = token_meta
            continue

        print("Processing vote #%s" % votenumber)
        votequestion = VoteQuestion(
            number=votenumber,
            session=session,
            date=vote_date,
            yea_total=int(vote.findtext('DecisionDivisionNumberOfYeas')),
            nay_total=int(vote.findtext('DecisionDivisionNumberOfNays')),
            paired_total=int(vote.findtext('DecisionDivisionNumberOfPaired')))
        if sum((votequestion.yea_total, votequestion.nay_total)) < 100:
            logger.error("Fewer than 100 votes on vote#%s" % votenumber)
        decision = vote.findtext('DecisionResultName')
        if decision in ('Agreed to', 'Agreed To'):
            votequestion.result = 'Y'
        elif decision == 'Negatived':
            votequestion.result = 'N'
        elif decision == 'Tie':
            votequestion.result = 'T'
        else:
            raise Exception("Couldn't process vote result %s in %s" % (decision, votelisturl))
        if vote.findtext('BillNumberCode'):
            billnumber = vote.findtext('BillNumberCode')
            try:
                votequestion.bill = Bill.objects.get(session=session, number=billnumber)
            except Bill.DoesNotExist:
                votequestion.bill = Bill.objects.create_temporary_bill(session=session, number=billnumber)
                logger.warning("Temporary bill %s created for vote %s" % (billnumber, votenumber))

        votequestion.description_en = vote.findtext('DecisionDivisionSubject')
        try:
            votequestion.description_fr = root_fr.xpath(
                'Vote/DecisionDivisionNumber[text()=%s]/../DecisionDivisionSubject/text()'
                % votenumber)[0]
        except Exception:
            logger.exception("Couldn't get french description for vote %s" % votenumber)

        votequestion.save()

        detailurl = VOTEDETAIL_URL.format(
            parliamentnum=session.parliamentnum,
            sessnum=session.sessnum,
            votenumber=votenumber,
        )
        resp = requests.get(detailurl)
        resp.raise_for_status()
        detailroot = etree.fromstring(resp.content)

        for voter in detailroot.findall('VoteParticipant'):
            pol = Politician.objects.get_by_parl_mp_id(
                voter.find('PersonId').text,
                session=session,
                riding_name=voter.find('ConstituencyName').text,
            )
            member = ElectedMember.objects.get_by_pol(
                politician=pol, date=votequestion.date
            )
            if voter.find('IsVoteYea').text == 'true':
                ballot = 'Y'
            elif voter.find('IsVoteNay').text == 'true':
                ballot = 'N'
            elif voter.find('IsVotePaired').text == 'true':
                ballot = 'P'
            else:
                display_name = getattr(pol, 'name', 'unknown')
                raise Exception(
                    "Couldn't parse RecordedVote for %s in vote %s" % (
                        display_name,
                        votenumber,
                    )
                )
            MemberVote(
                member=member,
                politician=pol,
                votequestion=votequestion,
                vote=ballot,
            ).save()
        votequestion.label_absent_members()
        votequestion.label_party_votes()
        for mv in votequestion.membervote_set.all():
            mv.save_activity()

        if (
            latest_timestamp is None
            or event_dt > latest_timestamp
            or (
                event_dt == latest_timestamp
                and token_meta['vote'] > latest_meta.get('vote', -1)
            )
        ):
            latest_timestamp = event_dt
            latest_token = token
            latest_meta = token_meta

    if latest_timestamp and (
        watermark.timestamp is None
        or latest_timestamp > watermark.timestamp
        or latest_token != watermark.token
    ):
        update_watermark(
            "votes",
            token=latest_token,
            timestamp=latest_timestamp,
            metadata=latest_meta,
        )

    return True
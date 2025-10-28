import type { HomePayload } from "../../lib/op-api";
import { BillListSection } from "./bill-list-section";
import { HansardTopicsSection } from "./hansard-topics-section";
import { HomeHero } from "./home-hero";
import { SiteNewsSection } from "./site-news-section";
import { VoteGridSection } from "./vote-grid-section";
import { TranscriptHighlightSection } from "./transcript-highlight-section";

// MARK: Component
interface HomePageProps {
  payload: HomePayload;
}

export function HomePage({ payload }: HomePageProps) {
  return (
    <main className="site-main">
      <HomeHero latestHansard={payload.latest_hansard} />
      <TranscriptHighlightSection
        latestHansard={payload.latest_hansard}
        summary={payload.hansard_summary}
        wordcloud={payload.wordcloud}
      />
      <HansardTopicsSection
        latestHansard={payload.latest_hansard}
        topics={payload.hansard_topics}
      />
      <BillListSection bills={payload.recently_debated_bills} />
      <VoteGridSection votes={payload.recent_votes} />
      <SiteNewsSection items={payload.site_news} />
    </main>
  );
}

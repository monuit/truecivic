from django.urls import path

from parliament.api.v1.views import (
    BillDetailAPIView,
    BillListAPIView,
    CommitteeListAPIView,
    DebateListAPIView,
    HomeAPIView,
    PoliticianListAPIView,
    SearchAPIView,
    VoteDetailAPIView,
    VoteListAPIView,
)

app_name = "api_v1"

urlpatterns = [
    path("home/", HomeAPIView.as_view(), name="home"),
    path("home", HomeAPIView.as_view(), name="home-no-slash"),
    path("bills/", BillListAPIView.as_view(), name="bill-list"),
    path("bills", BillListAPIView.as_view(), name="bill-list-no-slash"),
    path("bills/<str:session_id>/<str:bill_number>/",
         BillDetailAPIView.as_view(), name="bill-detail"),
    path(
        "bills/<str:session_id>/<str:bill_number>",
        BillDetailAPIView.as_view(),
        name="bill-detail-no-slash",
    ),
    path("politicians/", PoliticianListAPIView.as_view(), name="politician-list"),
    path("politicians", PoliticianListAPIView.as_view(),
         name="politician-list-no-slash"),
    path("debates/", DebateListAPIView.as_view(), name="debate-list"),
    path("debates", DebateListAPIView.as_view(), name="debate-list-no-slash"),
    path("committees/", CommitteeListAPIView.as_view(), name="committee-list"),
    path("committees", CommitteeListAPIView.as_view(),
         name="committee-list-no-slash"),
    path("votes/", VoteListAPIView.as_view(), name="vote-list"),
    path("votes", VoteListAPIView.as_view(), name="vote-list-no-slash"),
    path("votes/<str:session_id>/<str:number>/",
         VoteDetailAPIView.as_view(), name="vote-detail"),
    path("votes/<str:session_id>/<str:number>",
         VoteDetailAPIView.as_view(), name="vote-detail-no-slash"),
    path("search/", SearchAPIView.as_view(), name="search"),
    path("search", SearchAPIView.as_view(), name="search-no-slash"),
]

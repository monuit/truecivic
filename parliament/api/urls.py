from django.urls import include, path, re_path

from parliament.api.views import hansard, hansard_list
from parliament.rag.api_views import KnowledgeChunkListView
from parliament.rag.views import RagContextView

urlpatterns = [
    re_path(r'^hansards/(?P<hansard_id>\d+)/$',
            hansard, name='legacy_api_hansard'),
    re_path(r'^hansards/$', hansard_list, name='legacy_api_hansard_list'),
    path('v1/', include('parliament.api.v1.urls')),
    re_path(r'^rag/context/$', RagContextView.as_view(), name='rag_context'),
    re_path(r'^rag/chunks/$', KnowledgeChunkListView.as_view(),
            name='rag_chunk_list'),
]

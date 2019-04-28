from django.contrib.auth import get_user_model
from rest_framework.viewsets import ModelViewSet
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.viewsets import GenericViewSet
from rest_framework.mixins import ListModelMixin
from . import serializers as st_serializers
from . import models as st_models
from . import permissions as st_permissions
from .mixins import DisableListMixin


class SchoolViewSet(ModelViewSet):
    """
    학교 API
    
    retrieve:
    개별 학교 정보 조회
    
    list:
    전체 학교 목록 조회
    
    create:
    학교 생성
    
    update:
    학교 정보 수정
    
    partial_update:
    학교 정보 부분 수정
    
    delete:
    학교 삭제
    """
    serializer_class = st_serializers.SchoolSerializer
    permission_classes = (st_permissions.IsOwnerOrReadOnly,)
    queryset = st_models.School.objects.all().order_by('name')   # 이름 오름차순
    
    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)
    
    @action(detail=True, methods=['post'],
            permission_classes=(IsAuthenticated,))
    def subscribe(self, request, pk=None):
        """
        post:
        구독 설정
        """
        school = self.get_object()
        if school.subscribers.filter(id=request.user.id).exists():
            return Response('이미 구독 중 입니다.', status=status.HTTP_409_CONFLICT)
        school.subscribers.add(request.user)
        school.save()
        return Response('구독하였습니다.')

    @action(detail=True, methods=['delete'],
            permission_classes=(IsAuthenticated,))
    def unsubscribe(self, request, pk=None):
        """
        delete:
        구독 해제
        """
        school = self.get_object()
        if not school.subscribers.filter(id=request.user.id).exists():
            return Response('구독 중인 학교가 아닙니다.', status=status.HTTP_409_CONFLICT)
        school.subscribers.remove(request.user)
        school.save()
        return Response('구독을 취소 하였습니다.')


class ProfileViewSet(DisableListMixin, ModelViewSet):
    """
    로그인된 사용자의 프로필 API
    
    list:
    로그인된 사용자 프로필 조회
    
    create:
    사용자 프로필 추가
    
    update:
    로그인된 사용자 프로필 수정
    
    partial_update:
    로그인된 사용자 프로필 부분 수정
    
    delete:
    로그인된 사용자 탈퇴
    """
    permission_classes = (st_permissions.IsSelf,)    # 본인만 사용 가능하도록 제한
    # 프로필 조회시 학교 목록을 함께 쿼리 해오도록 prefetch_related 추가
    queryset = st_models.User.objects \
        .prefetch_related('schools') \
        .filter(is_active=True)
    serializer_class = st_serializers.ProfileSerializer
    
    @action(detail=False, methods=['post'],
            permission_classes=(AllowAny,))
    def registration(self, request):
        """ 사용자 가입 API """
        serialized = st_serializers.ProfileSerializer(data=request.data)
        if not serialized.is_valid():
            return Response(serialized.errors,
                            status=status.HTTP_400_BAD_REQUEST)
        
        get_user_model().objects.create_user(
            serialized.validated_data['username'],
            email=serialized.validated_data['email'],
            password=serialized.validated_data['password'],
            first_name=serialized.validated_data['first_name'],
            last_name=serialized.validated_data['last_name'],
        )
        serialized.validated_data.pop('password')
        return Response(serialized.validated_data,
                        status=status.HTTP_201_CREATED)


class ArticleViewSet(DisableListMixin, ModelViewSet):
    """
    글 API
    
    retrieve:
    개별 글 조회
    
    list:
    전체 글 목록 조회
    
    create:
    글 생성
    
    update:
    글 수정
    
    partial_update:
    글 부분 수정
    
    delete:
    글 삭제
    """
    permission_classes = (st_permissions.IsOwnerOrReadOnly,)
    serializer_class = st_serializers.ArticleSerializer
    queryset = st_models.Article.objects.all().order_by('-id')   # 최신글 내림차순

    def perform_create(self, serializer):
        article = serializer.save(owner=self.request.user)
        
        # 글이 작성된 학교의 구독자들의 피드에 글을 배달
        subscribers = article.school.subscribers.all()
        if subscribers.exists():
            article.receivers.add(*list(subscribers))
            article.save()


class NewsFeedViewSet(ListModelMixin, GenericViewSet):
    """
    뉴스피드 API
    
    list:
    로그인한 사용자에게 배달된 피드의 글 목록을 조회
    """
    permission_classes = (IsAuthenticated,)
    serializer_class = st_serializers.ArticleSerializer
    queryset = st_models.Article.objects \
        .prefetch_related('receivers') \
        .all().order_by('-id')  # 최신피드 내림차순
    
    def get_queryset(self):
        return self.queryset.filter(receivers__id=self.request.user.id)

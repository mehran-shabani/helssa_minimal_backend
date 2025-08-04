from django.urls import path

from .views import (RegisterOrLoginView, VerifyOTPView, CreateVisit,
                    UserProfileView, UserProfileUpdateView, BlogListView, BlogCommentsView,
                    CommentLikeDislikeView, CreateTransaction, ShowBoxMoneyView, VerifyPaymentView, DownloadAPKView, CreateSuperVisit, UserProfileViewJustUserName,
                    UserProfileUpdateViewJustUserName, download_order_file, order_verification)

urlpatterns = [
    path('register/', RegisterOrLoginView.as_view(), name='register_or_login'),
    path('verify/', VerifyOTPView.as_view(), name='verify_otp'),
    path('visit/', CreateVisit.as_view(), name='visit'),
    path('profile/', UserProfileView.as_view(), name='profile'),
    path('create-visit/', CreateVisit.as_view(), name='create-visit'),
    path('profile/update/', UserProfileUpdateView.as_view(), name='update-profile'),
    path('transaction/', CreateTransaction.as_view(), name='create-transaction'),
    path('blogs/', BlogListView.as_view(), name='blog-detail'),
    path('blogs/<int:blog_id>/comments/', BlogCommentsView.as_view(), name='blog-comments'),
    path('comments/<int:comment_id>/<str:actions>/', CommentLikeDislikeView.as_view(), name='comment-like-dislike'),
    path('box/', ShowBoxMoneyView.as_view(), name='box-money'),
    path('verify-payment/', VerifyPaymentView.as_view(), name='verify-payment'),
    path('download-apk/', DownloadAPKView.as_view(), name='download-apk'),
    path('super-visit/<int:cost>/', CreateSuperVisit.as_view(), name='create-super-visit'),
    path('username/', UserProfileViewJustUserName.as_view(), name='username'),
    path('username/update/', UserProfileUpdateViewJustUserName.as_view(), name='update-username'),
    path('order/verify/<str:national_code>/', order_verification, name='order-verification'),
    path('order/download/<str:national_code>/', download_order_file.as_view(), name='order-download'),
]

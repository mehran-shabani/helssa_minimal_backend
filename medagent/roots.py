from django.urls import path
from medagent import views

app_name = "medagent"

urlpatterns = [
    path("session/create/", views.CreateSession.as_view(), name="session-create"),
    path("session/message/", views.PostMessage.as_view(), name="session-message"),
    path("session/end/", views.EndSession.as_view(), name="session-end"),
    path("session/summary/", views.GetMedicalSummary.as_view(), name="patient-summary"),
]

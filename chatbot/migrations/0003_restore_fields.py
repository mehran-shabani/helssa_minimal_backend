from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("chatbot", "0002_historicalchatsession_toolcalllog_usagelog_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="chatsession",
            name="title",
            field=models.CharField(max_length=120, blank=True, default=""),
        ),
        migrations.AddField(
            model_name="chatsession",
            name="ended_at",
            field=models.DateTimeField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name="historicalchatsession",
            name="title",
            field=models.CharField(max_length=120, blank=True, default=""),
        ),
        migrations.AddField(
            model_name="historicalchatsession",
            name="ended_at",
            field=models.DateTimeField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name="chatsummary",
            name="last_message_id",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="chatsummary",
            name="is_stale",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="chatsummary",
            name="in_progress",
            field=models.BooleanField(default=False),
        ),
    ]

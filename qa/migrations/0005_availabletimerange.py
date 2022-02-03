# Generated by Django 3.1 on 2022-01-28 19:14

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('instructor', '0027_auto_20220121_1550'),
        ('qa', '0004_question_answer_needed_now'),
    ]

    operations = [
        migrations.CreateModel(
            name='AvailableTimeRange',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('weekday', models.IntegerField(choices=[(1, 'Monday'), (2, 'Tuesday'), (3, 'Wednesday'), (4, 'Thursday'), (5, 'Friday'), (6, 'Saturday'), (7, 'Sunday')])),
                ('start_time', models.TimeField()),
                ('end_time', models.TimeField()),
                ('coach', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='available_time_ranges', to='instructor.coach')),
            ],
        ),
    ]
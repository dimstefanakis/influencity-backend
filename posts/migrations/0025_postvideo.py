# Generated by Django 2.2.4 on 2020-11-14 00:37

from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('posts', '0024_auto_20201114_0144'),
    ]

    operations = [
        migrations.CreateModel(
            name='PostVideo',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('passthrough', models.UUIDField(default=uuid.uuid1)),
                ('asset_id', models.CharField(max_length=120)),
                ('post', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='posts.Post')),
            ],
        ),
    ]
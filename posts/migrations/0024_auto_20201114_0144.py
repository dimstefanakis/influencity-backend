# Generated by Django 2.2.4 on 2020-11-13 23:44

from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('posts', '0023_postvideo'),
    ]

    operations = [
        migrations.CreateModel(
            name='PostVideoAssetMetaData',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('passthrough', models.UUIDField(default=uuid.uuid1)),
                ('post', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='posts.Post')),
            ],
        ),
        migrations.DeleteModel(
            name='PostVideo',
        ),
    ]

# Generated by Django 2.2.4 on 2020-11-17 01:40

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0015_auto_20201030_0542'),
        ('posts', '0028_auto_20201116_0437'),
    ]

    operations = [
        migrations.AddField(
            model_name='post',
            name='linked_project',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='posts', to='projects.Project'),
        ),
    ]

# Generated by Django 3.1 on 2022-03-04 00:12

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('instructor', '0028_auto_20220225_0414'),
        ('expertisefields', '0008_expertisefieldsuggestion_suggested_by'),
    ]

    operations = [
        migrations.CreateModel(
            name='ExpertiseFieldMultiple',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('coach', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='expertise_fields', to='instructor.coach')),
            ],
        ),
    ]

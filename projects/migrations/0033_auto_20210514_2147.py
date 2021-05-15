# Generated by Django 3.1 on 2021-05-14 21:47

from decimal import Decimal
from django.db import migrations
import djmoney.models.fields


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0032_auto_20210514_0025'),
    ]

    operations = [
        migrations.AlterField(
            model_name='project',
            name='credit',
            field=djmoney.models.fields.MoneyField(blank=True, decimal_places=2, default=Decimal('10'), default_currency='USD', max_digits=7, null=True),
        ),
    ]

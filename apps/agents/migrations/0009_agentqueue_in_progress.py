# Generated by Django 3.2.9 on 2021-12-09 19:59

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('agents', '0008_auto_20211209_1954'),
    ]

    operations = [
        migrations.AddField(
            model_name='agentqueue',
            name='in_progress',
            field=models.BooleanField(default=False),
        ),
    ]

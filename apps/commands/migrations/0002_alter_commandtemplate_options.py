# Generated by Django 3.2.9 on 2021-12-09 18:02

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('commands', '0001_initial'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='commandtemplate',
            options={'ordering': ['-date_updated'], 'verbose_name': 'Command Template', 'verbose_name_plural': 'Command Templates'},
        ),
    ]

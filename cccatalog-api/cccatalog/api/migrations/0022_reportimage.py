# Generated by Django 2.2.10 on 2020-04-12 19:54

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0021_deletedimages'),
    ]

    operations = [
        migrations.CreateModel(
            name='ReportImage',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('identifier', models.UUIDField()),
                ('reason', models.CharField(choices=[('adult', 'adult'), ('dmca', 'dmca'), ('other', 'other')], max_length=10)),
                ('description', models.TextField(max_length=500)),
            ],
            options={
                'db_table': 'nsfw_reports',
            },
        ),
    ]

# Generated by Django 4.2.4 on 2023-08-19 13:19

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("shopapp", "0009_alter_product_description"),
    ]

    operations = [
        migrations.AlterField(
            model_name="product",
            name="description",
            field=models.TextField(blank=True, default=1),
            preserve_default=False,
        ),
    ]

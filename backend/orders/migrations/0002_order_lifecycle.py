from django.db import migrations, models


def migrate_order_statuses(apps, schema_editor):
    Order = apps.get_model("orders", "Order")
    Order.objects.filter(status="pending").update(status="pending_payment")


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0001_initial"),
    ]

    operations = [
        migrations.RenameField(
            model_name="order",
            old_name="user",
            new_name="buyer",
        ),
        migrations.AlterField(
            model_name="order",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending_payment", "Pending payment"),
                    ("paid", "Paid"),
                    ("confirmed", "Confirmed"),
                    ("shipped", "Shipped"),
                    ("delivered", "Delivered"),
                    ("completed", "Completed"),
                    ("cancelled", "Cancelled"),
                    ("payment_failed", "Payment failed"),
                    ("refunded", "Refunded"),
                ],
                db_index=True,
                default="pending_payment",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="order",
            name="buyer",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.SET_NULL,
                related_name="orders",
                to="accounts.user",
                db_index=True,
            ),
        ),
        migrations.AddField(
            model_name="orderitem",
            name="seller",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.SET_NULL,
                related_name="sold_items",
                to="accounts.user",
                db_index=True,
            ),
        ),
        migrations.AddField(
            model_name="orderitem",
            name="item_status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("confirmed", "Confirmed"),
                    ("shipped", "Shipped"),
                    ("delivered", "Delivered"),
                    ("completed", "Completed"),
                    ("cancelled", "Cancelled"),
                ],
                db_index=True,
                default="pending",
                max_length=20,
            ),
        ),
        migrations.RunPython(migrate_order_statuses, migrations.RunPython.noop),
    ]

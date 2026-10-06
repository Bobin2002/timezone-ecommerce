from django.contrib import admin

from .models import (
    Category,
    Product,
    Cart,
    CartItem,
    Order,
    OrderItem
)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('name',)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'name',
        'brand',
        'category',
        'price',
        'stock',
        'created_at',
    )

    list_filter = (
        'category',
        'brand',
        'created_at',
    )

    search_fields = (
        'name',
        'brand',
        'description',
    )

    ordering = ('-created_at',)


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'user',
        'created_at',
    )

    search_fields = (
        'user__username',
    )


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'cart',
        'product',
        'quantity',
    )


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'user',
        'total_amount',
        'status',
        'created_at',
    )

    list_filter = (
        'status',
        'created_at',
    )

    search_fields = (
        'user__username',
        'phone',
        'address',
    )

    ordering = ('-created_at',)

    inlines = [OrderItemInline]


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'order',
        'product',
        'quantity',
        'price',
    )


admin.site.site_header = "TimeZone Administration"
admin.site.site_title = "TimeZone Admin"
admin.site.index_title = "TimeZone Website Management"
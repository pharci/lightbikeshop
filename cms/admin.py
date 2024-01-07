from django.contrib import admin
from .models import SliderImage, FAQ
from django.utils.safestring import mark_safe

class SliderImageAdmin(admin.ModelAdmin):
    list_display = ('caption', 'order', 'image_preview')
    list_editable = ('order',)
    readonly_fields = ('image_preview',)

    def image_preview(self, obj):
        if obj.image:
            return mark_safe(f'<img src="{obj.image.url}" width="150" height="auto" />')
        return "Нет изображения"
    image_preview.short_description = "Предпросмотр"

class FAQAdmin(admin.ModelAdmin):
    list_display = ('caption', 'order')
    list_editable = ('order',)

admin.site.register(SliderImage, SliderImageAdmin)
admin.site.register(FAQ, FAQAdmin)
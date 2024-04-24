import django_filters
from django.db.models import Q
from .models import ProductVariant, Attribute, Brand, AttributeValue

def get_attribute_values(attribute_name):
    return Attribute.objects.get(name=attribute_name).values.all()

class ProductVariantFilter(django_filters.FilterSet):
    brand = django_filters.ModelMultipleChoiceFilter(
        field_name='product__brand',
        queryset=Brand.objects.all(),
        label='Бренды'
    )
    
    # Вместо конкретных атрибутов мы динамически добавим их в конструкторе
    class Meta:
        model = ProductVariant
        fields = ['brand']  # Изначально указываем только поля, не зависящие от атрибутов

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        attributes = Attribute.objects.filter(attribute_variants__is_filter=True).distinct()
        for attribute in attributes:
            self.filters[f'attribute_{attribute.id}'] = django_filters.ModelMultipleChoiceFilter(
                queryset=get_attribute_values(attribute),
                method=f'filter_attribute_{attribute.id}',
                label=attribute.name
            )
            # Добавляем метод фильтрации для каждого атрибута
            setattr(self, f'filter_attribute_{attribute.id}', self.make_attribute_filter(attribute))

    def make_attribute_filter(self, attribute):
        def filter_attribute(queryset, name, value):
            # Создаем фильтр для конкретного значения атрибута
            return queryset.filter(
                Q(attribute_variants__attribute=attribute) & 
                Q(attribute_variants__value__in=value)
            ).distinct()
        return filter_attribute
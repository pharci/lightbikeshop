from django.shortcuts import render, get_object_or_404
from .models import * 
from collections import defaultdict
from django.views.generic.list import ListView
from .filters import ProductFilter
from django.template.loader import render_to_string
from django.http import JsonResponse
from django.db.models import Case, When, Value, IntegerField

class ProductListCategoryView(ListView):
    model = ProductVariant
    paginate_by = 32
    template_name = 'store/products_list.html'
    
    def get_queryset(self):
        category_slug = self.kwargs.get('category_slug')
        selected_brands = self.request.GET.getlist('brand')
        selected_attributes = defaultdict(list)
        sort_option = self.request.GET.get('sort', 'price')

        for key in self.request.GET.keys():
            if key.startswith("attr_"):
                attr_slug = key.split("attr_")[1]
                values = self.request.GET.getlist(key)
                selected_attributes[attr_slug].extend(values)

        queryset = ProductFilter.get_variants_category(selected_brands, self.request, selected_attributes, category_slug)

        # Сортировка
        if sort_option:
            queryset = queryset.order_by(sort_option)

        return queryset


    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        category_slug = self.kwargs.get('category_slug', None)
        context['category'] = get_object_or_404(Category, slug=category_slug) if category_slug else None
        context['brands'] = ProductFilter.get_brands(category_slug)
        context['selected_brands'] = self.request.GET.getlist('brand')
        context['selected_attributes'] = self.request.GET
        context['remaining_items'] = min(context['page_obj'].paginator.per_page, (context['page_obj'].paginator.count - context['page_obj'].number * context['page_obj'].paginator.per_page) + self.paginate_by)
        context['attributes'] = ProductFilter.get_attributes_category(category_slug)

        return context
    
    def render_to_response(self, context, **response_kwargs):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            products_html = render_to_string('store/partials/product_list_cards.html', context, request=self.request)
            pagination_html = render_to_string('store/partials/product_list_pagination.html', context, request=self.request)
            is_last_page = not context['page_obj'].has_next()
            remaining_items = min(context['page_obj'].paginator.per_page, (context['page_obj'].paginator.count - context['page_obj'].number * context['page_obj'].paginator.per_page) + self.paginate_by)
            total_items = context['page_obj'].paginator.count
            return JsonResponse({
                'products_html': products_html,
                'pagination_html': pagination_html,
                'is_last_page': is_last_page,
                'remaining_items': remaining_items,
                'total_items': total_items,
                'per_page': context['page_obj'].paginator.per_page
            })
        else:
            return super().render_to_response(context, **response_kwargs)
    


class ProductListBrandView(ListView):
    model = ProductVariant
    paginate_by = 32
    template_name = 'store/products_list.html'
    
    def get_queryset(self):
        brand_slug = self.kwargs.get('brand_slug')
        selected_categories = self.request.GET.getlist('category')
        selected_attributes = defaultdict(list)
        sort_option = self.request.GET.get('sort', 'price')

        for key in self.request.GET.keys():
            if key.startswith("attr_"):
                attr_slug = key.split("attr_")[1]
                values = self.request.GET.getlist(key)
                selected_attributes[attr_slug].extend(values)

        queryset = ProductFilter.get_variants_brand(selected_categories, self.request, selected_attributes, brand_slug)

        # Сортировка
        if sort_option:
            queryset = queryset.order_by(sort_option)

        return queryset


    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        brand_slug = self.kwargs.get('brand_slug', None)
        context['brand'] = get_object_or_404(Brand, slug=brand_slug) if brand_slug else None
        context['categories'] = ProductFilter.get_categories(brand_slug)
        context['selected_categories'] = self.request.GET.getlist('category')
        context['selected_attributes'] = self.request.GET
        context['remaining_items'] = min(context['page_obj'].paginator.per_page, (context['page_obj'].paginator.count - context['page_obj'].number * context['page_obj'].paginator.per_page) + self.paginate_by)
        context['attributes'] = ProductFilter.get_attributes_brand(brand_slug)

        return context
    
    def render_to_response(self, context, **response_kwargs):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            products_html = render_to_string('store/partials/product_list_cards.html', context, request=self.request)
            pagination_html = render_to_string('store/partials/product_list_pagination.html', context, request=self.request)
            is_last_page = not context['page_obj'].has_next()
            remaining_items = min(context['page_obj'].paginator.per_page, (context['page_obj'].paginator.count - context['page_obj'].number * context['page_obj'].paginator.per_page) + self.paginate_by)
            total_items = context['page_obj'].paginator.count
            return JsonResponse({
                'products_html': products_html,
                'pagination_html': pagination_html,
                'is_last_page': is_last_page,
                'remaining_items': remaining_items,
                'total_items': total_items,
                'per_page': context['page_obj'].paginator.per_page
            })
        else:
            return super().render_to_response(context, **response_kwargs)


def product_detail(request, category_slug, brand_slug, sku, slug):
    variant = get_object_or_404(
        ProductVariant.objects.prefetch_related(
            'attribute_variants__attribute',
            'images'
        ),
        sku=sku
    )

    image_urls = [image.get_image_url() for image in variant.images.all()]
    
    attributes = variant.attribute_variants.all()

    all_variants = ProductVariant.objects.filter(product=variant.product).prefetch_related(
        'attribute_variants__attribute'
    )

    all_colors = AttributeVariant.objects.filter(
        variant__in=all_variants,
        attribute__slug='cvet'
    ).distinct().select_related('value')

    context = {
        'variant': variant,
        'attributes': attributes,
        'image_urls': image_urls,
        'all_colors': all_colors
    }

    return render(request, 'store/product_detail.html', context)




def catalog(request):

    categories = Category.objects.all()

    brands = Brand.objects.all()

    return render(request, 'store/catalog.html', {'brands': brands, 'categories': categories})


def brands(request):

    brands = Brand.objects.all()

    return render(request, 'store/brands.html', {'brands': brands})


class WishlistView(ListView):
    model = ProductVariant
    paginate_by = 32
    template_name = 'store/wishlist.html'
    
    def get_queryset(self):

        wishlist = Wishlist.objects.filter(user=self.request.user).first()

        if wishlist:
            wishlist_items = WishlistItem.objects.filter(wishlist=wishlist).select_related('product_variant')
            product_variants = [item.product_variant for item in wishlist_items]
            return product_variants
        else:
            return []

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if not self.request.user.is_authenticated:
            return render(self.request, 'store/login.html', {'message': 'Войдите, чтобы использовать избранное'})
        wishlist = Wishlist.objects.filter(user=self.request.user).first()
        if wishlist:
            count = WishlistItem.objects.filter(wishlist=wishlist).count()

        context['count_items'] = count
        context['remaining_items'] = min(context['page_obj'].paginator.per_page, (context['page_obj'].paginator.count - context['page_obj'].number * context['page_obj'].paginator.per_page) + self.paginate_by)
        return context
    
    def render_to_response(self, context, **response_kwargs):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            products_html = render_to_string('store/partials/product_list_cards.html', context, request=self.request)
            pagination_html = render_to_string('store/partials/product_list_pagination.html', context, request=self.request)
            is_last_page = not context['page_obj'].has_next()
            remaining_items = min(context['page_obj'].paginator.per_page, (context['page_obj'].paginator.count - context['page_obj'].number * context['page_obj'].paginator.per_page) + self.paginate_by)
            return JsonResponse({
                'products_html': products_html,
                'pagination_html': pagination_html,
                'is_last_page': is_last_page,
                'remaining_items': remaining_items
            })
        else:
            return super().render_to_response(context, **response_kwargs)



def add_to_wishlist(request, variant_id):
    user = request.user
    if not user.is_authenticated:
        return JsonResponse({'error': 'Authentication required'}, status=401)

    product_variant = get_object_or_404(ProductVariant, pk=variant_id)
    wishlist, _ = Wishlist.objects.get_or_create(user=user)
    
    wishlist_item, created = WishlistItem.objects.get_or_create(
        wishlist=wishlist,
        product_variant=product_variant
    )
    
    if not created:
        wishlist_item.delete()
        return JsonResponse({'added': False})
    
    return JsonResponse({'added': True})
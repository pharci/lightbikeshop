from django.shortcuts import render, get_object_or_404
from .models import * 
from django.db.models import Case, When

def product_list(request, category=None, brand=None):
    context = {}
    products = None

    if category:
        category = get_object_or_404(Category, slug=category)
        products = Product.objects.filter(category=category)
        context['category'] = category

    elif brand:
        brand = get_object_or_404(Brand, slug=brand)
        products = Product.objects.filter(brand=brand)
        context['brand'] = brand

    elif request.method == 'GET' and 'q' in request.GET:
        query = request.GET.get('q')
        products = Product.objects.filter(name__icontains=query)

    else:
        # Если не указаны категория, бренд или поисковый запрос - показать все продукты
        products = Product.objects.all()

    # Сортировка по статусу доступности
    if products:
        # Сначала товары в наличии, затем под заказ, затем скоро будет, и в конце - нет в наличии
        # Порядок сортировки: in_stock, on_order, coming_soon, out_of_stock
        products = products.order_by(
            Case(
                When(availability_status='in_stock', then=0),
				When(availability_status='coming_soon', then=1),
                When(availability_status='on_order', then=2),
                When(availability_status='out_of_stock', then=3),
                default=4,
                output_field=models.IntegerField(),
            )
        )
        context['products'] = products
    else:
        context['notfound'] = True

    return render(request, 'products/products_list.html', context)


def product_detail(request, category_slug, id, slug):

	product = get_object_or_404(Product, id=id, slug=slug)

	context = {'product': product}

	return render(request, 'products/product_detail.html', context)

def catalog(request):
    categories = Category.objects.all().order_by('name')
    other_slugs = ['workshop', 'clothes', 'protection']
    other_categories = categories.filter(slug__in=other_slugs)
    main_categories = categories.exclude(slug__in=other_slugs)
    
    brands = Brand.objects.all()
    
    return render(request, 'products/catalog.html', {
        'brands': brands,
        'main_categories': main_categories,
        'other_categories': other_categories
        })
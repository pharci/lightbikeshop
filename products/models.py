from django.db import models
from django.urls import reverse

class Category(models.Model):
	slug = models.SlugField('Название в ссылке', max_length=200, db_index=True, unique=True)
	name = models.CharField('Название', max_length=200, db_index=True)
	image = models.ImageField(upload_to='categories/')

	class Meta:
		ordering = ('name',)
		verbose_name = 'Категория'
		verbose_name_plural = 'Категории'

	def __str__(self):
		return self.name

	def get_absolute_url(self):
		return reverse('products:product_list_by_category', args=[self.slug])

class Brand(models.Model):
	slug = models.SlugField('Название в ссылке', max_length=200, db_index=True, unique=True)
	image = models.ImageField(upload_to='brends/')
	title = models.CharField(max_length=100)

	def __str__(self):
		return self.title

	def get_absolute_url(self):
		return reverse('products:product_list_by_brand', args=[self.slug])

class Product(models.Model):
	category = models.ForeignKey(Category, null=True, on_delete=models.PROTECT)
	brand = models.ForeignKey(Brand, null=True, blank=True, on_delete=models.CASCADE)
	name = models.CharField('Название', max_length=200)
	available_andrey = models.BooleanField('Есть в наличии у Андрея', default=True)
	available_damir = models.BooleanField('Есть в наличии у Дамира', default=True)
	price = models.FloatField('Цена')
	count = models.PositiveSmallIntegerField('Количество в наличии', null=True)
	new = models.BooleanField('Новый?', default=True)
	rec = models.BooleanField('Рекоммендуемый?', default=False)
	image = models.ImageField('Картинка', null=True, blank=True, upload_to='products/')
	description = models.TextField('Описание')
	created = models.DateTimeField('Дата создания', auto_now_add=True)
	updated = models.DateTimeField('Дата последнего обновления', auto_now=True)
	slug = models.SlugField('Название в ссылке', max_length=200, db_index=True)

	def __str__(self):
		return self.name

	class Meta:
		ordering = ('name',)
		verbose_name = 'Товар'
		verbose_name_plural = 'Товары'

	@property
	def imageURL(self):
		try:
			url = self.image.url
		except:
			url = ''
		return url

	def get_absolute_url(self):
		return reverse('products:product_detail', args=[self.category.slug, self.id, self.slug])
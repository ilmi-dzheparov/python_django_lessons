"""
В этом модуле лежат различные наборы представлений
для интернет-магазина: по товарам, по заказам и т.д.
"""

from timeit import default_timer

from django.contrib.auth.mixins import (
    LoginRequiredMixin,
    PermissionRequiredMixin,
    UserPassesTestMixin,
)
from django.contrib.auth.models import Group

from django.http import HttpResponse, HttpRequest, HttpResponseRedirect, JsonResponse
from django.shortcuts import render, redirect, reverse
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import (
    TemplateView,
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    DeleteView,
)
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, OpenApiResponse

from shopapp.forms import ProductForm, OrderForm, GroupForm
from shopapp.models import Product, Order, ProductImage

from rest_framework.viewsets import ModelViewSet
from rest_framework.filters import SearchFilter, OrderingFilter
from .serializers import ProductSerializer, OrderSerializer


@extend_schema(description="Product views CRUD")
class ProductViewSet(ModelViewSet):
    """
    Набор представлений для действий над Product.

    Полный CRUD для сущностей товара
    """

    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    filter_backends = [
        SearchFilter,
        DjangoFilterBackend,
        OrderingFilter,
    ]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "price", "discount"]
    filterset_fields = [
        "name",
        "description",
        "price",
        "discount",
        "archived",
    ]

    @extend_schema(
        summary="Get one product by ID",
        description="Retrieves product, returns 404 if not found",
        responses={
            200: ProductSerializer,
            404: OpenApiResponse(description="Empty response, product by ID not found"),
        },
    )
    def retrieve(self, *args, **kwargs):
        return super().retrieve(*args, **kwargs)


class OrderViewSet(ModelViewSet):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    filter_backends = [
        # SearchFilter,
        DjangoFilterBackend,
        OrderingFilter,
    ]
    # search_fields = ["user", "description"]
    ordering_fields = ["user", "created_at"]
    filterset_fields = [
        "user",
        "delivery_address",
        "promocode",
    ]


class ShopIndexView(View):
    def get(self, request: HttpRequest) -> HttpResponse:
        products = [
            ("Laptop", 1999),
            ("Desktop", 2999),
            ("Smartphone", 999),
        ]
        context = {
            "time_running": default_timer(),
            "products": products,
        }
        return render(request, "shopapp/shop-index.html", context=context)


class GroupsListView(View):
    def get(self, request: HttpRequest) -> HttpResponse:
        context = {
            "form": GroupForm(),
            "groups": Group.objects.prefetch_related("permissions").all(),
        }
        return render(request, "shopapp/groups-list.html", context=context)

    def post(self, request: HttpRequest):
        form = GroupForm(request.POST)
        if form.is_valid():
            form.save()
        return redirect(request.path)


class ProductDetailView(DetailView):
    template_name = "shopapp/products-detail.html"
    # model = Product
    queryset = Product.objects.prefetch_related("images")
    context_object_name = "product"

    # def get(self, request: HttpRequest, pk: int) -> HttpResponse:
    #     product = get_object_or_404(Product, pk=pk) #Product.objects.get(pk=pk)
    #     context = {
    #         "product": product,
    #     }
    #     return render(request, 'shopapp/products-detail.html', context=context)


class ProductsListView(ListView):
    template_name = "shopapp/products-list.html"
    # model = Product
    queryset = Product.objects.filter(archived=False)
    context_object_name = "products"

    # def get_context_data(self, **kwargs):
    #     context = super().get_context_data(**kwargs)
    #     context["products"] = Product.objects.all()
    #     return context


class OrdersListView(LoginRequiredMixin, ListView):
    queryset = (Order.objects
                # .select_related("user")
                .prefetch_related("products"))


# def orders_list(request: HttpRequest):
#     context = {
#         "orders": Order.objects.select_related("user").prefetch_related("products").all()
#     }
#     return render(request, "shopapp/order_list.html", context=context)


class OrderDetailView(PermissionRequiredMixin, DetailView):
    permission_required = ["shopapp.view_order"]
    queryset = Order.objects.select_related("user").prefetch_related("products")
    context_object_name = "order"


class ProductCreateView(PermissionRequiredMixin, CreateView):
    permission_required = [
        "shopapp.add_product",
    ]
    model = Product
    # fields = "name", "price", "description", "discount
    form_class = ProductForm
    success_url = reverse_lazy("shopapp:products_list")

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.save()
        return super().form_valid(form)


# def create_product(request: HttpRequest):
#     if request.method == "POST":
#         form = ProductForm(request.POST)
#         if form.is_valid():
#             # name = form.cleaned_data["name"]
#             # price = form.cleaned_data["price"]
#             Product.objects.create(**form.cleaned_data)
#             url = reverse("shopapp:products_list")
#             return redirect(url)
#     else:
#         form = ProductForm()
#     context = {
#         "form": form,
#     }
#     return render(request, "shopapp/product_form.html", context=context)


class ProductUpdateView(UserPassesTestMixin, UpdateView):
    def test_func(self):
        # return  self.request.user.groups.filter(name="secret-group").exists
        return self.request.user.is_superuser or (
            self.request.user.has_perm("shopapp.add_product")
            and self.get_object().created_by == self.request.user
        )

    model = Product
    # fields = "name", "price", "description", "discount", "preview"
    form_class = ProductForm
    template_name_suffix = "_update_form"

    def get_success_url(self):
        return reverse(
            "shopapp:products_detail",
            kwargs={"pk": self.object.pk},
        )

    def form_valid(self, form):
        response = super().form_valid(form)
        for image in form.files.getlist("images"):
            ProductImage.objects.create(product=self.object, image=image)
        return response


class ProductDeleteView(DeleteView):
    model = Product
    success_url = reverse_lazy("shopapp:products_list")

    def form_valid(self, form):
        success_url = self.get_success_url()
        self.object.archived = True
        self.object.save()
        return HttpResponseRedirect(success_url)


class OrderCreateView(CreateView):
    model = Order
    # fields = "delivery_address", "promocode", "user", "products"
    success_url = reverse_lazy("shopapp:orders_list")
    form_class = OrderForm

    def form_valid(self, form):
        form.save()
        products = form.cleaned_data["products"]
        for product in products:
            form.instance.products.add(product)
        return super().form_valid(form)


class OrderUpdateView(UpdateView):
    model = Order
    success_url = reverse_lazy("shopapp:orders_list")
    form_class = OrderForm
    template_name_suffix = "_update_form"

    def form_valid(self, form):
        form.save()
        products = form.cleaned_data["products"]
        for product in products:
            form.instance.products.add(product)
        return super().form_valid(form)

    def get_success_url(self):
        return reverse(
            "shopapp:order_detail",
            kwargs={"pk": self.object.pk},
        )


class OrderDeleteView(DeleteView):
    model = Order
    success_url = reverse_lazy("shopapp:orders_list")
    # def form_valid(self, form):
    #     success_url = self.get_success_url()
    #     self.object.archived = True
    #     self.object.save()
    #     return HttpResponseRedirect(success_url)


# def create_order(request: HttpRequest):
#
#     if request.method == "POST":
#         form = OrderForm(request.POST)
#         if form.is_valid():
#             delivery_address = form.cleaned_data["delivery_address"]
#             promocode = form.cleaned_data["promocode"]
#             user = form.cleaned_data["user"]
#             products = form.cleaned_data['products']
#             obj = Order(
#                 delivery_address = delivery_address,
#                 promocode = promocode,
#                 user = user,
#             )
#             obj.save()
#             for elem in products:
#                 obj.products.add(elem)
#
#             url = reverse("shopapp:orders_list")
#             return redirect(url)
#     else:
#         print('ERROR')
#         form = OrderForm()
#     context = {
#         "form": form,
#     }
#     return render(request, "shopapp/order_form.html", context=context)


class ProductsDataExportView(View):
    def get(self, request: HttpRequest) -> HttpResponse:
        products = Product.objects.order_by("pk").all()
        products_data = [
            {
                "pk": product.pk,
                "name": product.name,
                "price": product.price,
                "archived": product.archived,
            }
            for product in products
        ]
        return JsonResponse({"products": products_data})


class StaffRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_staff


# @staff_member_required
class OrdersDataExportView(StaffRequiredMixin, View):
    def get(self, request: HttpRequest) -> JsonResponse:
        orders = Order.objects.order_by("pk").all()
        orders_data = [
            {
                "pk": order.pk,
                "delivery_address": order.delivery_address,
                "promocode": order.promocode,
                "user_id": order.user,
                "orders_list": [product.pk for product in order.products],
            }
            for order in orders
        ]
        return JsonResponse({"orders": orders_data})

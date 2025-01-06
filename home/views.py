from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.template.loader import render_to_string

import razorpay
from django.urls import reverse

from .models import Dish
from collections import defaultdict
from django.shortcuts import render, redirect
import json
from django.views.decorators.csrf import csrf_exempt

from django.utils.crypto import get_random_string
ORDER_START = 100
order_counter = ORDER_START
# Create your views here.

@login_required(login_url='accounts/login/')  # Redirect to login page if not authenticated
def index(request):
    return render(request, 'pages/index.html')

@login_required
def login_view(request):
    # Replace with your actual login logic or template
    if request.user.is_authenticated:
        return redirect('index')  # Redirect to index if already authenticated
    return render(request, 'pages/login.html')




@login_required
def agent_page(request):
    return render(request, 'pages/agent.html')




@login_required
def order_page(request):
    try:
        # Get filter options and search term from the GET request
        search_term = request.GET.get('search', '')
        veg_option = request.GET.get('veg_option', 'all')
        category = request.GET.get('category', 'all')

        # Query the Dish model for active dishes
        active_dishes = Dish.objects.filter(is_active=True)

        # Apply filters
        if veg_option != 'all':
            active_dishes = active_dishes.filter(veg_nonveg=veg_option)

        if category != 'all':
            active_dishes = active_dishes.filter(category=category)

        if search_term:
            active_dishes = active_dishes.filter(name__icontains=search_term)

        # Group dishes by category
        dishes_by_category = defaultdict(list)
        for dish in active_dishes:
            dishes_by_category[dish.category].append(dish)

        # Filter out empty categories
        dishes_by_category = {
            category: dishes
            for category, dishes in dishes_by_category.items()
            if dishes
        }

        # Count the number of filtered dishes
        dish_count = active_dishes.count()

        # Prepare context
        context = {
            'dishes_by_category': dishes_by_category,
            'category_choices': Dish.CATEGORY_CHOICES,
            'selected_veg_option': veg_option,
            'selected_category': category,
            'VEG_NONVEG_CHOICES': Dish.VEG_NONVEG_CHOICES,
            'search_term': search_term,
            'dish_count': dish_count,  # Pass the count to the template
        }

        # Check if it's an AJAX request
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

        if is_ajax:
            html = render_to_string(
                'pages/filtered_dishes.html',
                context,
                request=request
            )
            return HttpResponse(html)

        # Regular request - return full page
        return render(request, 'pages/order.html', context)

    except Exception as e:
        # Log the error (you should configure proper logging)
        print(f"Error in order_page view: {str(e)}")

        # If it's an AJAX request, return an error message
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            error_html = '<div class="text-center py-4 text-danger">Server error occurred. Please try again.</div>'
            return HttpResponse(error_html, status=500)

        # For regular requests, return the full page with an error message
        error_context = {
            'error_message': "An error occurred while processing your request. Please try again later."
        }
        return render(request, 'pages/order.html', error_context)



@login_required
def order_status(request):
    return render(request, 'pages/order_status.html')


"""@login_required
def payment_page(request):
    # Retrieve checkout data from the session
    checkout_data = request.session.get('checkout_data', {})

    # Redirect to the cart if there's no checkout data
    if not checkout_data:
        return redirect('cart')

    # Prepare context for the template
    context = {
        "user_name": checkout_data.get('user_name', 'Guest'),
        "phone_number": checkout_data.get('phone_number', 'Not Provided'),
        "total_bill": checkout_data.get('total_bill', 0),
        "total_quantity": checkout_data.get('total_quantity', 0),
        "items": checkout_data.get('items', []),
        "dish_quantities": checkout_data.get('dish_quantities', {}),  # Include dish quantities
    }

    # Render the payment page with the context
    return render(request, 'pages/payment_page.html', context)"""


@login_required
def profile_page(request):
    return render(request, 'pages/profile_page.html')


@login_required
@csrf_exempt
def checkout(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Invalid request method."}, status=405)

    try:
        # Parse JSON data from the request
        data = json.loads(request.body)
        cart = data.get("cart", [])

        # Validate the cart
        if not cart or not isinstance(cart, list):
            return JsonResponse({"success": False, "error": "Cart is empty or invalid format."}, status=400)

        total_bill = 0
        total_quantity = 0
        detailed_items = []
        dish_quantities = {}  # To store quantities keyed by dish name or ID

        # Fetch user details
        user = request.user
        user_name = user.first_name  # Use full name if available
        phone_number = getattr(getattr(user, 'userprofile', None), 'phone_number', "Not Provided")
        print(f"Processing checkout for User: {user_name}, Phone: {phone_number}")

        for item in cart:
            dish_id = item.get("id")
            quantity = item.get("quantity")

            # Validate dish ID and quantity
            if not dish_id or not isinstance(quantity, int) or quantity <= 0:
                return JsonResponse({
                    "success": False,
                    "error": f"Invalid dish ID or quantity for item: {item}"
                }, status=400)

            try:
                # Fetch the dish and ensure it's active
                dish = Dish.objects.get(id=dish_id, is_active=True)
            except Dish.DoesNotExist:
                return JsonResponse({
                    "success": False,
                    "error": f"Dish with ID {dish_id} does not exist or is inactive."
                }, status=404)

            # Calculate the total price for the dish
            total_price = float(dish.price) * quantity
            total_bill += total_price
            total_quantity += quantity

            # Add the dish details to the checkout items
            detailed_items.append({
                "name": dish.name,
                "quantity": quantity,
                "price": float(dish.price),
                "total_price": total_price,
            })

            # Store quantity keyed by dish name
            dish_quantities[dish.name] = quantity

            # Debugging: Print dish details for verification
            print(f"Dish: {dish.name}, Price: {dish.price}, Quantity: {quantity}, Total Price: {total_price}")

        # Store checkout data in the session
        request.session['checkout_data'] = {
            "user_name": user_name,
            "phone_number": phone_number,
            "total_bill": total_bill,
            "total_quantity": total_quantity,
            "items": detailed_items,
            "dish_quantities": dish_quantities,  # Include dish quantities
        }

        print(f"Checkout data stored for user {user_name} with total bill ₹{total_bill}")

        # Respond with a success message and redirect URL
        return JsonResponse({
            "success": True,
            "redirect_url": reverse('payment')  # Ensure 'payment' is a valid URL name in your Django app
        })

    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "Invalid JSON format."}, status=400)
    except Exception as e:
        print(f"Exception during checkout: {str(e)}")
        return JsonResponse({"success": False, "error": "An unexpected error occurred."}, status=500)


# Razorpay API credentials
RAZORPAY_KEY_ID = "rzp_test_ntWJV3wwyFK3tP"
RAZORPAY_KEY_SECRET = "jdbKxd6SAgin9aZq2UU5uKLx"




def check_payment_status(request):
    """Check if payment is already completed or failed"""
    payment_status = request.session.get('payment_status', None)
    order_id = request.session.get('order_id', None)

    if order_id:
        if payment_status == 'success':
            return redirect('order_success')
        elif payment_status == 'failed':
            return redirect('order_failed')
    return None


@login_required
def payment_page(request):
    # Check if payment already processed
    redirect_response = check_payment_status(request)
    if redirect_response:
        return redirect_response

    # Retrieve checkout data from the session
    checkout_data = request.session.get('checkout_data', {})

    # Redirect to the cart if there's no checkout data
    if not checkout_data:
        return redirect('order')

    try:
        # Calculate total bill
        total_bill = checkout_data.get('total_bill', 0) * 100  # Amount in paisa

        # Initialize Razorpay client
        client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

        # Create Razorpay order
        order = client.order.create({
            "amount": total_bill,
            "currency": "INR",
            "payment_capture": "1"
        })

        # Store order ID and set payment status as pending
        request.session['current_order_id'] = order['id']
        request.session['payment_status'] = 'pending'

        # Prepare context for the template
        context = {
            "user_name": checkout_data.get('user_name', 'Guest'),
            "phone_number": checkout_data.get('phone_number', 'Not Provided'),
            "total_bill": checkout_data.get('total_bill', 0),
            "total_quantity": checkout_data.get('total_quantity', 0),
            "items": checkout_data.get('items', []),
            "dish_quantities": checkout_data.get('dish_quantities', {}),
            "razorpay_order_id": order['id'],
            "razorpay_key_id": RAZORPAY_KEY_ID,
            "currency": "INR",
        }

        return render(request, 'pages/payment_page.html', context)

    except Exception as e:
        print(f"Payment page error: {str(e)}")
        return redirect('cart')


@csrf_exempt
def verify_payment(request):
    if request.method == "POST":
        try:
            # Parse the request body
            data = json.loads(request.body)

            # Verify this order belongs to current session
            current_order_id = request.session.get('current_order_id')
            if current_order_id != data.get("razorpay_order_id"):
                raise Exception("Invalid order ID")

            # Initialize Razorpay client
            client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

            # Verify the payment signature
            client.utility.verify_payment_signature({
                "razorpay_order_id": data["razorpay_order_id"],
                "razorpay_payment_id": data["razorpay_payment_id"],
                "razorpay_signature": data["razorpay_signature"],
            })

            # Update payment status and store order details
            request.session["payment_status"] = "success"
            request.session["order_id"] = data["razorpay_order_id"]
            request.session["payment_id"] = data["razorpay_payment_id"]
            request.session["total_bill"] = data.get("amount", 0) / 100
            request.session["total_quantity"] = data.get("total_quantity", 0)

            return JsonResponse({"success": True, "redirect_url": "/order-success/"})

        except razorpay.errors.SignatureVerificationError as e:
            request.session["payment_status"] = "failed"
            return JsonResponse({"success": False, "error": "Signature verification failed: " + str(e)})

        except Exception as e:
            request.session["payment_status"] = "failed"
            return JsonResponse({"success": False, "error": str(e)})

    return JsonResponse({"success": False, "error": "Invalid request method"})


@login_required
def order_success(request):
    # Verify payment was successful
    if request.session.get('payment_status') != 'success':
        return redirect('cart')

    # Context to pass data to the success page
    context = {
        "order_id": request.session.get("order_id", "N/A"),
        "total_bill": request.session.get("total_bill", 0),
        "total_quantity": request.session.get("total_quantity", 0),
    }

    # Clear checkout and payment data
    for key in ['checkout_data', 'current_order_id', 'payment_status']:
        request.session.pop(key, None)

    return render(request, 'pages/order_success.html', context)


@login_required
def order_failed(request):
    # Verify payment actually failed
    if request.session.get('payment_status') != 'failed':
        return redirect('cart')

    # Clear checkout and payment data
    for key in ['checkout_data', 'current_order_id', 'payment_status']:
        request.session.pop(key, None)

    return render(request, 'pages/order_failed.html')


@login_required
@csrf_exempt
def clear_order_data(request):
    if request.method == "POST":
        # Clear specific order-related data instead of entire session
        keys_to_clear = [
            'checkout_data',
            'current_order_id',
            'payment_status',
            'order_id',
            'payment_id',
            'total_bill',
            'total_quantity'
        ]
        for key in keys_to_clear:
            request.session.pop(key, None)
        return JsonResponse({"success": True})
    return JsonResponse({"error": "Invalid request"}, status=400)
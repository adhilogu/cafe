from django.db.models import Count, Q, Sum
from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.db.models import Q, Sum

import razorpay
from django.urls import reverse

from .models import Dish,UserProfile,OrderStatus,PlacedOrder
from collections import defaultdict
from django.shortcuts import render, redirect
import json
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
import uuid
from django.views.decorators.csrf import csrf_exempt



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
@csrf_exempt
def agent_page(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)

            # Handle status toggle
            if "status" in data:
                status = data.get("status")

                if status not in ['online', 'offline']:
                    print(f"Invalid status received: {status}")
                    return JsonResponse({"success": False, "error": "Invalid status. Must be 'online' or 'offline'."},
                                        status=400)

                try:
                    user_profile = request.user.userprofile
                except UserProfile.DoesNotExist:
                    print(f"No UserProfile found for user: {request.user.username}")
                    return JsonResponse({"success": False, "error": "User profile not found."}, status=404)

                if user_profile.role != 'agent':
                    print(f"User {request.user.username} attempted to update status but role is {user_profile.role}")
                    return JsonResponse({"success": False, "error": "Only agents can update status."}, status=403)

                # Update agent_status
                new_status = (status == 'online')
                if user_profile.agent_status != new_status:
                    user_profile.agent_status = new_status
                    user_profile.save()
                    print(f"Updated agent_status for {request.user.username} to {new_status}")
                else:
                    print(f"No change needed for {request.user.username}, agent_status already {new_status}")

                return JsonResponse({"success": True})

            # Handle order status update
            elif "order_id" in data and "new_status" in data:
                order_id = data.get("order_id")
                new_status = data.get("new_status")

                try:
                    user_profile = request.user.userprofile
                except UserProfile.DoesNotExist:
                    return JsonResponse({"success": False, "error": "User profile not found."}, status=404)

                if user_profile.role != 'agent':
                    return JsonResponse({"success": False, "error": "Only agents can update order status."}, status=403)

                # Get the order
                try:
                    order = OrderStatus.objects.get(order_id=order_id)

                    # Check if agent is assigned to this order
                    if not order.agents.filter(id=user_profile.id).exists():
                        return JsonResponse({"success": False, "error": "You are not assigned to this order."},
                                            status=403)

                    # Update order status
                    order.order_status = new_status
                    order.save()

                    return JsonResponse({"success": True, "message": "Order status updated successfully"})

                except OrderStatus.DoesNotExist:
                    return JsonResponse({"success": False, "error": "Order not found."}, status=404)

            else:
                return JsonResponse({"success": False, "error": "Invalid request data."}, status=400)

        except json.JSONDecodeError as e:
            print(f"JSON decode error: {str(e)}")
            return JsonResponse({"success": False, "error": "Invalid JSON format."}, status=400)
        except Exception as e:
            print(f"Unexpected error in agent_page: {str(e)}")
            return JsonResponse({"success": False, "error": f"An unexpected error occurred: {str(e)}"}, status=500)

    # GET request - Display orders
    try:
        user_profile = request.user.userprofile
    except UserProfile.DoesNotExist:
        return render(request, 'pages/agent.html', {'error': 'User profile not found'})

    if user_profile.role != 'agent':
        return render(request, 'pages/agent.html', {'error': 'Access denied. Agent role required.'})

    # Get orders assigned to this agent
    assigned_orders = OrderStatus.objects.filter(
        agents=user_profile
    ).order_by('-ordered_time')

    # Separate completed and pending orders
    completed_orders = assigned_orders.filter(order_status='out_for_delivery').order_by('-ordered_time')
    pending_orders = assigned_orders.filter(
        Q(order_status='preparing') | Q(order_status='declined')
    ).order_by('-ordered_time')

    # Get dishes for each order
    orders_with_dishes = []
    for order in pending_orders:
        dishes = PlacedOrder.objects.filter(order_id=order.order_id)
        orders_with_dishes.append({
            'order': order,
            'dishes': dishes
        })

    completed_orders_with_dishes = []
    for order in completed_orders:
        dishes = PlacedOrder.objects.filter(order_id=order.order_id)
        completed_orders_with_dishes.append({
            'order': order,
            'dishes': dishes
        })

    # Calculate statistics
    total_tasks = assigned_orders.count()
    completed_tasks = completed_orders.count()
    incomplete_tasks = pending_orders.count()

    # Handle search
    search_query = request.GET.get('search', '')
    if search_query:
        orders_with_dishes = [
            item for item in orders_with_dishes
            if search_query.lower() in item['order'].order_id.lower()
        ]
        completed_orders_with_dishes = [
            item for item in completed_orders_with_dishes
            if search_query.lower() in item['order'].order_id.lower()
        ]

    context = {
        'pending_orders': orders_with_dishes,
        'completed_orders': completed_orders_with_dishes,
        'total_tasks': total_tasks,
        'completed_tasks': completed_tasks,
        'incomplete_tasks': incomplete_tasks,
        'search_query': search_query,
    }

    return render(request, 'pages/agent.html', context)


@login_required
def order_page(request):
    try:
        search_term = request.GET.get('search', '')
        veg_option = request.GET.get('veg_option', 'all')
        category = request.GET.get('category', 'all')

        # Check for active agents
        active_agents_available = UserProfile.objects.filter(
            role='agent',
            agent_status=True
        ).exists()

        # If no active agents, return empty context
        if not active_agents_available:
            context = {
                'active_agents_available': False,
            }
            return render(request, 'pages/order.html', context)

        # Proceed with normal dish filtering only if agents are available
        active_dishes = Dish.objects.filter(is_active=True)

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

        dish_count = active_dishes.count()

        context = {
            'dishes_by_category': dishes_by_category,
            'category_choices': Dish.CATEGORY_CHOICES,
            'selected_veg_option': veg_option,
            'selected_category': category,
            'VEG_NONVEG_CHOICES': Dish.VEG_NONVEG_CHOICES,
            'search_term': search_term,
            'dish_count': dish_count,
            'active_agents_available': True,
        }

        # Check if it's an AJAX request
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

        if is_ajax:
            # For AJAX requests, still check agent availability
            if not active_agents_available:
                error_html = '''
                <div class="col-12 text-center py-4">
                    <p style="color: red; font-size: 1.5rem; font-weight: bold;">
                        <i class="fas fa-exclamation-circle" style="margin-right: 10px;"></i>
                        No active agents available
                    </p>
                </div>
                '''
                return HttpResponse(error_html)

            html = render_to_string(
                'pages/filtered_dishes.html',
                context,
                request=request
            )
            return HttpResponse(html)

        return render(request, 'pages/order.html', context)

    except Exception as e:
        print(f"Error in order_page view: {str(e)}")

        # For AJAX requests, return error message
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            error_html = '''
            <div class="text-center py-4 text-danger">
                <i class="fas fa-exclamation-triangle fa-2x mb-2"></i>
                <div>Server error occurred. Please try again.</div>
            </div>
            '''
            return HttpResponse(error_html, status=500)

        # For regular requests, return error page
        error_context = {
            'active_agents_available': False,
            'error_message': "An error occurred while processing your request. Please try again later."
        }
        return render(request, 'pages/order.html', error_context)



@login_required
def profile_page(request):
    return render(request, 'pages/profile_page.html')


@login_required
@csrf_exempt
def checkout(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Invalid request method."}, status=405)

    try:
        data = json.loads(request.body)
        cart = data.get("cart", [])

        if not cart or not isinstance(cart, list):
            return JsonResponse({"success": False, "error": "Cart is empty or invalid format."}, status=400)

        total_bill = 0
        total_quantity = 0
        detailed_items = []
        dish_quantities = {}

        user = request.user
        user_name = user.first_name or user.username
        phone_number = getattr(getattr(user, 'userprofile', None), 'phone_number', "Not Provided")
        print(f"Processing checkout for User: {user_name}, Phone: {phone_number}")

        for item in cart:
            dish_id = item.get("id")
            quantity = item.get("quantity")

            if not dish_id or not isinstance(quantity, int) or quantity <= 0:
                return JsonResponse({
                    "success": False,
                    "error": f"Invalid dish ID or quantity for item: {item}"
                }, status=400)

            try:
                dish = Dish.objects.get(id=dish_id, is_active=True)
            except Dish.DoesNotExist:
                return JsonResponse({
                    "success": False,
                    "error": f"Dish with ID {dish_id} does not exist or is inactive."
                }, status=404)

            total_price = float(dish.price) * quantity
            total_bill += total_price
            total_quantity += quantity

            detailed_items.append({
                "name": dish.name,
                "quantity": quantity,
                "price": float(dish.price),
                "total_price": total_price,
            })

            dish_quantities[dish.name] = quantity
            print(f"Dish: {dish.name}, Price: {dish.price}, Quantity: {quantity}, Total Price: {total_price}")

        request.session['checkout_data'] = {
            "user_name": user_name,
            "phone_number": phone_number,
            "total_bill": total_bill,
            "total_quantity": total_quantity,
            "items": detailed_items,
            "dish_quantities": dish_quantities,
        }

        print(f"Checkout data stored for user {user_name} with total bill ₹{total_bill}")

        return JsonResponse({
            "success": True,
            "redirect_url": reverse('payment')
        })

    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "Invalid JSON format."}, status=400)
    except Exception as e:
        print(f"Exception during checkout: {str(e)}")
        return JsonResponse({"success": False, "error": "An unexpected error occurred."}, status=500)


RAZORPAY_KEY_ID = "rzp_test_ntWJV3wwyFK3tP"
RAZORPAY_KEY_SECRET = "jdbKxd6SAgin9aZq2UU5uKLx"


@login_required
@csrf_exempt
def order_status(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            action = data.get("action")

            if action == "search":
                order_id = data.get("order_id")
                if not order_id:
                    return JsonResponse({"success": False, "error": "Order ID is required"}, status=400)

                # Build name variants
                name_variants = [
                    request.user.username,
                    request.user.email,
                    request.user.get_full_name(),
                ]
                if request.user.first_name:
                    name_variants.append(request.user.first_name)

                order_status = OrderStatus.objects.filter(
                    order_id__icontains=order_id,
                    order_name__in=name_variants
                ).first()

                if not order_status:
                    return JsonResponse({"success": False, "error": "Order not found"}, status=404)

                placed_orders = PlacedOrder.objects.filter(
                    order_id=order_status.order_id
                )

                items = [
                    {
                        "name": po.dish_name,
                        "quantity": po.dish_quantity,
                        "price": float(po.dish_price),
                        "total_price": float(po.dish_price) * po.dish_quantity
                    }
                    for po in placed_orders
                ]

                order_data = {
                    "order_id": order_status.order_id,
                    "order_name": order_status.order_name,
                    "order_phonenumber": order_status.order_phonenumber,
                    "agents": [agent.user.username for agent in order_status.agents.all()],
                    "order_status": order_status.order_status,
                    "bill_value": float(order_status.bill_value),
                    "ordered_time": order_status.ordered_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "items": items,
                    "total_quantity": sum(item["quantity"] for item in items)
                }

                return JsonResponse({"success": True, "order": order_data})

            elif action == "recent":
                # Build name variants
                name_variants = [
                    request.user.username,
                    request.user.email,
                    request.user.get_full_name(),
                ]
                if request.user.first_name:
                    name_variants.append(request.user.first_name)

                recent_orders = OrderStatus.objects.filter(
                    order_name__in=name_variants
                ).order_by('-ordered_time')[:5]

                orders_data = []
                for order_status in recent_orders:
                    placed_orders = PlacedOrder.objects.filter(
                        order_id=order_status.order_id
                    )

                    items = [
                        {
                            "name": po.dish_name,
                            "quantity": po.dish_quantity,
                            "price": float(po.dish_price),
                            "total_price": float(po.dish_price) * po.dish_quantity
                        }
                        for po in placed_orders
                    ]

                    order_data = {
                        "order_id": order_status.order_id,
                        "order_name": order_status.order_name,
                        "order_phonenumber": order_status.order_phonenumber,
                        "agents": [agent.user.username for agent in order_status.agents.all()],
                        "order_status": order_status.order_status,
                        "bill_value": float(order_status.bill_value),
                        "ordered_time": order_status.ordered_time.strftime("%Y-%m-%d %H:%M:%S"),
                        "items": items,
                        "total_quantity": sum(item["quantity"] for item in items)
                    }
                    orders_data.append(order_data)

                return JsonResponse({"success": True, "orders": orders_data})

            else:
                return JsonResponse({"success": False, "error": "Invalid action"}, status=400)

        except json.JSONDecodeError:
            return JsonResponse({"success": False, "error": "Invalid JSON format"}, status=400)
        except Exception as e:
            print(f"Error in order_status view (POST): {str(e)}")
            return JsonResponse({"success": False, "error": "An error occurred"}, status=500)

    # For GET requests, fetch user's orders from OrderStatus and PlacedOrder
    try:
        # Build name variants to match against order_name
        name_variants = [
            request.user.username,
            request.user.email,
            request.user.get_full_name(),
        ]
        if request.user.first_name:
            name_variants.append(request.user.first_name)
            if ' ' in request.user.first_name:
                name_variants.append(request.user.first_name.split()[0])

        # Debug: Check what's in the database
        all_orders = OrderStatus.objects.all()

        # Log all unique order_name values
        unique_names = OrderStatus.objects.values_list('order_name', flat=True).distinct()


        # Fetch pending orders
        pending_orders = OrderStatus.objects.filter(
            order_name__in=name_variants,
            order_status__in=['preparing', 'out_for_delivery']
        ).prefetch_related('agents__user').order_by('-ordered_time')

        # Fetch completed orders
        completed_orders = OrderStatus.objects.filter(
            order_name__in=name_variants,
            order_status='delivered'
        ).prefetch_related('agents__user').order_by('-ordered_time')


        # Attach PlacedOrder items and total_quantity to each order
        for order in pending_orders:
            order.items = PlacedOrder.objects.filter(order_id=order.order_id)
            order.total_quantity = order.items.aggregate(total=Sum('dish_quantity'))['total'] or 0
            print(
                f"Pending order {order.order_id}: {order.items.count()} items, Total Qty: {order.total_quantity}, Order Name: '{order.order_name}'")

        for order in completed_orders:
            order.items = PlacedOrder.objects.filter(order_id=order.order_id)
            order.total_quantity = order.items.aggregate(total=Sum('dish_quantity'))['total'] or 0
            print(
                f"Completed order {order.order_id}: {order.items.count()} items, Total Qty: {order.total_quantity}, Order Name: '{order.order_name}'")

        context = {
            'pending_orders': pending_orders,
            'completed_orders': completed_orders,

        }

    except Exception as e:
        print(f"Error fetching orders in order_status view (GET): {str(e)}")
        import traceback
        traceback.print_exc()
        context = {
            'pending_orders': [],
            'completed_orders': [],
            'error_message': "An error occurred while fetching your orders. Please try again later.",
            'debug_info': f"Error: {str(e)}",
        }

    return render(request, 'pages/order_status.html', context)

def check_payment_status(request):
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
    redirect_response = check_payment_status(request)
    if redirect_response:
        return redirect_response

    checkout_data = request.session.get('checkout_data', {})

    if not checkout_data:
        return redirect('order')

    try:
        total_bill = checkout_data.get('total_bill', 0) * 100

        client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

        order = client.order.create({
            "amount": total_bill,
            "currency": "INR",
            "payment_capture": "1"
        })

        request.session['current_order_id'] = order['id']
        request.session['payment_status'] = 'pending'

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
        return redirect('order')


@csrf_exempt
def verify_payment(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            current_order_id = request.session.get('current_order_id')
            if current_order_id != data.get("razorpay_order_id"):
                raise Exception("Invalid order ID")

            client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

            client.utility.verify_payment_signature({
                "razorpay_order_id": data["razorpay_order_id"],
                "razorpay_payment_id": data["razorpay_payment_id"],
                "razorpay_signature": data["razorpay_signature"],
            })

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
    if request.session.get('payment_status') != 'success':
        print("Redirecting to order page: payment_status is not success")
        return redirect('order')

    checkout_data = request.session.get('checkout_data', {})
    if not checkout_data:
        print("Redirecting to order page: checkout_data is empty")
        return redirect('order')

    order_id = request.session.get("order_id", "N/A")
    payment_id = request.session.get("payment_id", "N/A")
    total_bill = checkout_data.get("total_bill", 0)
    total_quantity = checkout_data.get("total_quantity", 0)
    user_name = checkout_data.get('user_name', 'Guest')
    phone_number = checkout_data.get('phone_number', 'Not Provided')
    items = checkout_data.get('items', [])

    unique_order_id = f"ORD-{uuid.uuid4().hex[:8].upper()}"

    try:
        # Find an available agent with role='agent', agent_status=True, and fewest active orders
        available_agents = UserProfile.objects.filter(
            role='agent',
            agent_status=True
        ).annotate(
            active_orders=Count('assigned_orders', filter=~Q(assigned_orders__order_status__in=['delivered', 'declined']))
        ).order_by('active_orders')

        if not available_agents.exists():
            print("No available agents with agent_status=True")
            for key in ['checkout_data', 'current_order_id', 'payment_status', 'order_id', 'payment_id', 'total_bill', 'total_quantity']:
                request.session.pop(key, None)
            context = {
                "error": "All agents are busy",
                "user_name": user_name,
                "total_bill": total_bill,
            }
            return render(request, 'pages/order_failed.html', context)

        # Select the agent with the fewest active orders
        selected_agent = available_agents.first()
        agent_username = selected_agent.user.username
        agent_number = selected_agent.phone_number or "Not Provided"
        print(f"Assigning order {unique_order_id} to agent: {agent_username} ({agent_number})")

        # Create PlacedOrder entries
        for item in items:
            placed_order = PlacedOrder.objects.create(
                order_id=unique_order_id,
                transaction_type='online',
                transaction_number=payment_id,
                order_name=user_name,
                order_phonenumber=phone_number,
                dish_name=item['name'],
                dish_quantity=item['quantity'],
                dish_price=item['price'],
                prep_status='preparing',
                ordered_time=timezone.now()
            )
            print(f"Created PlacedOrder: {placed_order}")

        # Create OrderStatus entry with agent assignment
        order_status = OrderStatus.objects.create(
            order_id=unique_order_id,
            transaction_type='online',
            order_name=user_name,
            order_phonenumber=phone_number,
            order_status='preparing',
            bill_value=total_bill,
            ordered_time=timezone.now(),
            agent_number=agent_number
        )
        order_status.agents.add(selected_agent)
        print(f"Created OrderStatus: {order_status} assigned to {agent_username}")

        print(f"Order created successfully: {unique_order_id} for {user_name}, assigned to {agent_username}")

        context = {
            "order_id": unique_order_id,
            "razorpay_order_id": order_id,
            "payment_id": payment_id,
            "total_bill": float(total_bill),
            "total_quantity": total_quantity,
            "user_name": user_name,
            "phone_number": phone_number,
            "items": items,
            "order_status": "preparing",
        }

        # Clear session data
        for key in ['checkout_data', 'current_order_id', 'payment_status', 'order_id', 'payment_id', 'total_bill', 'total_quantity']:
            request.session.pop(key, None)

        return render(request, 'pages/order_success.html', context)

    except Exception as e:
        print(f"Error creating order: {str(e)}")
        for key in ['checkout_data', 'current_order_id', 'payment_status', 'order_id', 'payment_id', 'total_bill', 'total_quantity']:
            request.session.pop(key, None)

        context = {
            "error": "Order creation failed. Please contact support.",
            "user_name": user_name,
            "total_bill": total_bill,
        }
        return render(request, 'pages/order_failed.html', context)

@login_required
def order_failed(request):
    if request.session.get('payment_status') != 'failed':
        return redirect('order')

    checkout_data = request.session.get('checkout_data', {})
    user_name = checkout_data.get('user_name', 'Guest')
    total_bill = checkout_data.get('total_bill', 0)

    # Clear session data
    for key in ['checkout_data', 'current_order_id', 'payment_status', 'order_id', 'payment_id', 'total_bill', 'total_quantity']:
        request.session.pop(key, None)

    context = {
        "error": request.session.get('error_message', "Order creation failed. Please try again."),
        "user_name": user_name,
        "total_bill": total_bill,
    }
    return render(request, 'pages/order_failed.html', context)


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
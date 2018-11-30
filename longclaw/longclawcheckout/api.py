"""
Shipping logic and payment capture API
"""
from django.utils import timezone
from django.db import transaction
from rest_framework.decorators import api_view, permission_classes
from rest_framework import permissions, status
from rest_framework.response import Response
from longclaw.longclawbasket.utils import destroy_basket
from longclaw.longclawcheckout.utils import create_order, GATEWAY
from longclaw.longclawcheckout.errors import PaymentError

@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def create_token(request):
    """ Generic function for creating a payment token from the
    payment backend. Some payment backends (e.g. braintree) support creating a payment
    token, which should be imported from the backend as 'get_token'
    """
    token = GATEWAY.get_token(request)
    return Response({'token': token}, status=status.HTTP_200_OK)

@transaction.atomic
@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def create_order_with_token(request):
    """
    Create an order using an existing transaction ID.
    This is useful for capturing the payment outside of
    longclaw - e.g. using paypals' express checkout or
    similar
    """
    # Get the request data
    try:
        address = request.data['address']
        shipping_option = request.data.get('shipping_option', None)
        email = request.data['email']
        transaction_id = request.data['transaction_id']
    except KeyError:
        return Response(data={"message": "Missing parameters from request data"},
                        status=status.HTTP_400_BAD_REQUEST)

    # Create the order
    order = create_order(
        email,
        request,
        addresses=address,
        shipping_option=shipping_option,
    )

    order.payment_date = timezone.now()
    order.transaction_id = transaction_id
    order.save()
    # Once the order has been successfully taken, we can empty the basket
    destroy_basket(request)

    return Response(data={"order_id": order.id}, status=status.HTTP_201_CREATED)

@transaction.atomic
@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def capture_payment(request):
    """
    Capture the payment for a basket and create an order

    request.data should contain:

    'address': Dict with the following fields:
        shipping_name
        shipping_address_line1
        shipping_address_city
        shipping_address_zip
        shipping_address_country
        billing_name
        billing_address_line1
        billing_address_city
        billing_address_zip
        billing_address_country

    'email': Email address of the customer
    'shipping': The shipping rate (in the sites' currency)
    """
    # get request data
    # import pdb; pdb.set_trace()
    different_billing_address = request.data.get('different_billing_address', None)
    if different_billing_address == "on":
        dba = True
    else:
        # address = request.data['address']
        address = {}
        address["shipping_address_line1"] = request.data.get('shipping-line_1')
        address["shipping_name"] = request.data.get('shipping-name')
        address["shipping_address_country"] = request.data.get('shipping-country')
        address["shipping_address_city"] = request.data.get('shipping-city')
        address["shipping_address_zip"] = request.data.get('shipping-postcode')
        email = request.data.get('email', None)
        shipping_option = request.data.get('shipping_option', None)

        # Capture the payment
        order = create_order(
            email,
            request,
            addresses=address,
            shipping_option=shipping_option,
            capture_payment=True
        )
        response = Response(data={"order_id": order.id},
                            status=status.HTTP_201_CREATED)

        return response

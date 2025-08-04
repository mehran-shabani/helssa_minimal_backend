import requests


def bitpay_request_payment(self, api_key, redirect_url, amount, order_id):
    data = {
        'api': api_key,
        'redirect': redirect_url,
        'amount': amount,
        'factorId': order_id,
    }

    response = requests.post('https://bitpay.ir/payment/gateway-send', data=data)

    if response > 0:
        return response
    else:
        return {'status': -1, 'message': 'Failed to connect to the payment gateway.'}

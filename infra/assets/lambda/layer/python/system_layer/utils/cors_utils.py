def cors_enabler(func):
    def inner_function(*args, **kwargs):
        result = func(*args, **kwargs)
        result['headers'] = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': '*',
            'Access-Control-Allow-Headers': '*',
            'Access-Control-Allow-Credentials': True
        }

        return result

    return inner_function

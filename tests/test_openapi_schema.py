#!/usr/bin/env python3
"""
Test script to verify OpenAPI schema generation and security schemes.
"""

import requests
import json

def test_openapi_schema():
    """Test the OpenAPI schema generation."""
    try:
        response = requests.get('http://127.0.0.1:8000/docs/schema/', timeout=5)
        if response.status_code == 200:
            schema = response.json()
            print('OpenAPI schema generated successfully!')

            # Check basic info
            info = schema.get('info', {})
            print(f'Title: {info.get("title", "N/A")}')
            print(f'Version: {info.get("version", "N/A")}')

            # Check security schemes
            components = schema.get('components', {})
            security_schemes = components.get('securitySchemes', {})
            if 'Bearer' in security_schemes:
                print('Bearer security scheme found!')
                bearer = security_schemes['Bearer']
                print(f'   Type: {bearer.get("type")}')
                print(f'   Scheme: {bearer.get("scheme")}')
                print(f'   Bearer Format: {bearer.get("bearerFormat")}')
            else:
                print('Bearer security scheme NOT found!')
                print(f'   Available schemes: {list(security_schemes.keys())}')

            # Check global security
            security = schema.get('security', [])
            if security:
                print(f'Global security: {security}')
            else:
                print('No global security defined')

            return True

        else:
            print(f'Schema request failed with status: {response.status_code}')
            print(f'Response: {response.text[:500]}')
            return False

    except requests.exceptions.RequestException as e:
        print(f'Server not available or connection error: {e}')
        print('Note: This test requires the Django server to be running')
        return False
    except Exception as e:
        print(f'Error: {e}')
        return False

if __name__ == '__main__':
    success = test_openapi_schema()
    if success:
        print("OpenAPI schema test passed!")
    else:
        print("OpenAPI schema test failed or server not available.")

from django.shortcuts import redirect
from django.conf import settings
from django.http import JsonResponse

class LoginRequiredMiddleware:
    """
    Middleware that requires user authentication for all views,
    except for admin, accounts (authentication), and integrations (webhooks).
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        
        # 1. Allow authenticated traffic, admin paths, auth views, and webhooks
        if (
            request.user.is_authenticated or
            path.startswith('/accounts/') or
            path.startswith('/admin/') or
            path.startswith('/integrations/')
        ):
            return self.get_response(request)

        # 2. Return 401 JSON for AJAX/fetch API requests
        if (
            request.headers.get('x-requested-with') == 'XMLHttpRequest' or
            request.content_type == 'application/json' or
            path.startswith('/jobs/generate/') or
            path.startswith('/jobs/discovery-status/') or
            path.startswith('/jobs/bulk-')
        ):
            return JsonResponse({
                "success": False,
                "error": "Authentication required."
            }, status=401)
        
        # 3. Redirect standard page requests to login page with next redirect query
        login_url = getattr(settings, 'LOGIN_URL', '/accounts/login/')
        return redirect(f"{login_url}?next={path}")

from django.shortcuts import render
from django.http import JsonResponse
from django.core.files.storage import FileSystemStorage
from .utils import extract_profile_from_pdf
import json
import os
from django.conf import settings

def profile_setup(request):
    if request.method == 'POST':
        # Handle file upload
        pdf_file = request.FILES.get('resume')
        linkedin_url = request.POST.get('linkedin_url', '')
        github_url = request.POST.get('github_url', '')

        if not pdf_file:
            return JsonResponse({'error': 'No resume uploaded'}, status=400)

        # Save the uploaded file temporarily
        fs = FileSystemStorage()
        filename = fs.save(pdf_file.name, pdf_file)
        uploaded_file_url = fs.path(filename)

        try:
            # Extract profile using Gemini
            profile_data = extract_profile_from_pdf(uploaded_file_url)
            
            # Add URLs
            profile_data['linkedin_url'] = linkedin_url
            profile_data['github_url'] = github_url

            # Save to master_profile.json
            profile_path = os.path.join(settings.BASE_DIR, 'master_profile.json')
            with open(profile_path, 'w') as f:
                json.dump(profile_data, f, indent=4)

            # Cleanup temp file
            os.remove(uploaded_file_url)

            return JsonResponse({
                'success': True, 
                'message': 'Profile successfully saved!',
                'data': profile_data
            })
        except Exception as e:
            # Cleanup temp file on error
            if os.path.exists(uploaded_file_url):
                os.remove(uploaded_file_url)
            return JsonResponse({'error': str(e)}, status=500)

    # If GET, check if profile exists to prepopulate
    profile_path = os.path.join(settings.BASE_DIR, 'master_profile.json')
    has_profile = os.path.exists(profile_path)
    
    return render(request, 'core/profile.html', {'has_profile': has_profile})

def job_discovery(request):
    profile_path = os.path.join(settings.BASE_DIR, 'master_profile.json')
    has_profile = os.path.exists(profile_path)
    
    if request.method == 'POST':
        if not has_profile:
            return JsonResponse({'error': 'Please set up your Master Profile first.'}, status=400)
            
        job_url = request.POST.get('job_url', '')
        job_description = request.POST.get('job_description', '')
        
        if not job_description:
            return JsonResponse({'error': 'Job Description is required.'}, status=400)
            
        with open(profile_path, 'r') as f:
            master_profile = json.load(f)
            
        try:
            from .utils import match_job_to_profile
            match_results = match_job_to_profile(master_profile, job_description)
            
            # Save a draft application to DB
            from .models import Application
            app_record = Application.objects.create(
                job_url=job_url,
                job_description=job_description,
                match_score=match_results.get('match_score', 0)
            )
            
            return JsonResponse({
                'success': True,
                'data': match_results,
                'app_id': app_record.id
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    return render(request, 'core/jobs.html', {'has_profile': has_profile})

def generate_kit(request):
    if request.method == 'POST':
        app_id = request.POST.get('app_id')
        if not app_id:
            return JsonResponse({'error': 'Application ID missing'}, status=400)
            
        from .models import Application
        from .utils import generate_application_kit
        
        try:
            app_record = Application.objects.get(id=app_id)
            
            profile_path = os.path.join(settings.BASE_DIR, 'master_profile.json')
            with open(profile_path, 'r') as f:
                master_profile = json.load(f)
                
            kit_data = generate_application_kit(master_profile, app_record.job_description)
            
            # Save the kit into the database
            app_record.tailored_resume = kit_data.get('tailored_resume')
            app_record.cover_letter = kit_data.get('cover_letter')
            app_record.save()
            
            return JsonResponse({
                'success': True,
                'data': kit_data
            })
            
        except Application.DoesNotExist:
            return JsonResponse({'error': 'Application record not found.'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'Invalid request method'}, status=405)

def mark_submitted(request):
    if request.method == 'POST':
        app_id = request.POST.get('app_id')
        if not app_id:
            return JsonResponse({'error': 'Application ID missing'}, status=400)
            
        from .models import Application
        try:
            app_record = Application.objects.get(id=app_id)
            app_record.mark_submitted()
            return JsonResponse({'success': True, 'message': 'Application tracked successfully!'})
        except Application.DoesNotExist:
            return JsonResponse({'error': 'Application record not found.'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
            
    return JsonResponse({'error': 'Invalid request method'}, status=405)

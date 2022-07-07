from django.urls import reverse_lazy
from django.template.loader import render_to_string
from django.conf import settings
import django_filters.views
from guardian.shortcuts import get_objects_for_user
from guardian.mixins import PermissionRequiredMixin
from apps.projects import models
from apps.projects import forms
from apps.projects import filters
from apps.account.models import User
from core.tasks import send_mail_task
from vulnman.core.views import generics
from vulnman.core.mixins import VulnmanPermissionRequiredMixin, ObjectPermissionRequiredMixin


class ProjectList(django_filters.views.FilterMixin, generics.VulnmanAuthListView):
    template_name = "projects/project_list.html"
    context_object_name = "projects"
    filterset_class = filters.ProjectFilter

    def get_queryset(self):
        qs = models.Project.objects.for_user(self.request.user)
        if not self.request.GET.get("status"):
            qs = qs.filter(status=models.Project.PENTEST_STATUS_OPEN)
        filterset = self.filterset_class(self.request.GET, queryset=qs)
        return filterset.qs

    def get_context_data(self, **kwargs):
        if self.request.GET and not self.request.session.get("project_filters"):
            self.request.session["project_filters"] = dict(self.request.GET)
        if not self.request.GET:
            self.request.session["project_filters"] = {}
        for key, value in self.request.GET.items():
            self.request.session["project_filters"][key] = value
        qs = models.Project.objects.for_user(self.request.user)
        qs_filters = self.request.GET.copy()
        if qs_filters.get("status"):
            del qs_filters["status"]
        filterset = self.filterset_class(qs_filters, queryset=qs)
        qs = filterset.qs
        kwargs["open_status_count"] = qs.filter(
            status=models.Project.PENTEST_STATUS_OPEN).count()
        kwargs["closed_status_count"] = qs.filter(
            status=models.Project.PENTEST_STATUS_CLOSED).count()
        return super().get_context_data(**kwargs)

    def get(self, request, *args, **kwargs):
        if self.request.session.get('project_pk'):
            del self.request.session['project_pk']
        return super().get(request, *args, **kwargs)


class ProjectCreate(VulnmanPermissionRequiredMixin, generics.VulnmanCreateView):
    form_class = forms.ProjectForm
    model = models.Project
    success_url = reverse_lazy("projects:project-list")
    permission_required = "projects.add_project"
    template_name = "projects/project_create.html"

    def form_valid(self, form):
        form.instance.creator = self.request.user
        return super().form_valid(form)


class ProjectDetail(VulnmanPermissionRequiredMixin, generics.VulnmanAuthDetailView):
    template_name = "projects/project_detail.html"
    permission_required = ["projects.view_project"]

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        context = self.get_context_data(object=self.object)
        if self.object:
            self.request.session['project_pk'] = str(self.get_object().pk)
        return self.render_to_response(context)

    def get_queryset(self):
        qs = models.Project.objects.for_user(self.request.user)
        return qs.filter(pk=self.kwargs.get("pk"))


class ProjectUpdate(VulnmanPermissionRequiredMixin, generics.VulnmanAuthUpdateView):
    template_name = "projects/project_create.html"
    form_class = forms.ProjectForm
    permission_required = ["projects.change_project"]

    def get_success_url(self):
        return reverse_lazy('projects:project-detail', kwargs={'pk': self.kwargs.get('pk')})

    def get_queryset(self):
        qs = models.Project.objects.for_user(self.request.user, perms="projects.change_project")
        return qs.filter(pk=self.kwargs.get("pk"))


class ProjectUpdateClose(PermissionRequiredMixin, generics.ProjectRedirectView):
    http_method_names = ["post"]
    url = reverse_lazy("projects:project-list")
    return_403 = True
    raise_exception = True
    permission_required = ["projects.change_project"]

    def get_permission_object(self):
        return self.get_project()

    def post(self, request, *args, **kwargs):
        obj = self.get_project()
        obj.status = models.Project.PENTEST_STATUS_CLOSED
        obj.save()
        obj.archive_project()
        return super().post(request, *args, **kwargs)


class ClientList(ObjectPermissionRequiredMixin, generics.VulnmanAuthListView):
    template_name = "projects/client_list.html"
    context_object_name = "clients"
    model = models.Client
    permission_required = ["projects.view_client"]
    raise_exception = True
    return_403 = True


class ClientDetail(VulnmanPermissionRequiredMixin, generics.VulnmanAuthDetailView):
    template_name = "projects/client_detail.html"
    context_object_name = "client"
    model = models.Client
    permission_required = ["projects.view_client"]


class ClientCreate(VulnmanPermissionRequiredMixin, generics.VulnmanAuthCreateWithInlinesView):
    # TODO: deprecate *inlinesview
    # TODO: write tests
    template_name = "projects/client_create.html"
    model = models.Client
    permission_required = ["projects.add_client"]
    form_class = forms.ClientForm
    inlines = [forms.ClientContactInline]


class ProjectContributorList(generics.ProjectListView):
    template_name = "projects/contributor_list.html"
    model = models.ProjectContributor
    permission_required = ["projects.view_project"]
    context_object_name = "contributors"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["create_form"] = forms.ContributorForm(project=self.get_project())
        return context


class ProjectContributorCreate(generics.ProjectCreateView):
    # TODO: do we need the "pk" here?
    http_method_names = ["post"]
    permission_required = ["projects.add_contributor"]
    form_class = forms.ContributorForm

    def get_success_url(self):
        return reverse_lazy("projects:contributor-list", kwargs={"pk": self.get_project().pk})

    def form_valid(self, form):
        user = User.objects.filter(username=form.cleaned_data.get('username'))
        if not user.exists():
            form.add_error("username", "Username not found!")
            return super().form_invalid(form)
        form.instance.user = user.get()
        if settings.EMAIL_BACKEND:
            send_mail_task.delay(
                "vulnman - New Project %s" % self.get_project().name,
                render_to_string("emails/new_project_contributor.html", context={
                    "obj": form.instance, "request": self.request, "project": self.get_project()}),
                form.instance.user.email
            )
        return super().form_valid(form)


class ProjectContributorDelete(generics.ProjectDeleteView):
    http_method_names = ["post"]
    permission_required = ["projects.add_contributor"]

    def get_queryset(self):
        return models.ProjectContributor.objects.filter(pk=self.kwargs.get("pk"), project=self.get_project())

    def get_success_url(self):
        return reverse_lazy("projects:contributor-list", kwargs={"pk": self.get_project().pk})


class ProjectTokenList(generics.ProjectListView):
    template_name = "projects/token_list.html"
    context_object_name = "tokens"
    permission_required = ["projects.view_project"]

    def get_queryset(self):
        return models.ProjectAPIToken.objects.filter(user=self.request.user, project=self.get_project())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["token_create_form"] = forms.ProjectAPITokenForm()
        return context


class ProjectTokenCreate(generics.ProjectCreateView):
    http_method_names = ["post"]
    form_class = forms.ProjectAPITokenForm
    success_url = reverse_lazy("projects:token-list")
    permission_required = ["projects.change_project"]

    def get_queryset(self):
        return models.ProjectAPIToken.objects.filter(project=self.get_project(), user=self.request.user)

    def form_valid(self, form):
        form.instance.project = self.get_project()
        form.instance.user = self.request.user
        return super().form_valid(form)


class ProjectTokenDelete(generics.ProjectDeleteView):
    http_method_names = ["post"]
    success_url = reverse_lazy("projects:token-list")

    def get_queryset(self):
        return models.ProjectAPIToken.objects.filter(
            project=self.get_project(), user=self.request.user)

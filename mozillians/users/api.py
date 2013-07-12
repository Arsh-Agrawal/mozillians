from urllib2 import unquote
from urlparse import urljoin

from django.conf import settings

from elasticutils.contrib.django import F, S
from tastypie import fields
from tastypie import http
from tastypie.bundle import Bundle
from tastypie.exceptions import ImmediateHttpResponse
from tastypie.resources import ModelResource
from tastypie.serializers import Serializer

from mozillians.api.authenticators import AppAuthentication
from mozillians.api.authorisers import MozillaOfficialAuthorization
from mozillians.api.paginator import Paginator
from mozillians.api.resources import ClientCachedResource
from mozillians.users.models import UserProfile


class UserResource(ClientCachedResource, ModelResource):
    """User Resource."""
    email = fields.CharField(attribute='user__email', null=True, readonly=True)
    groups = fields.CharField()
    skills = fields.CharField()
    languages = fields.CharField()

    class Meta:
        queryset = UserProfile.objects.all()
        authentication = AppAuthentication()
        authorization = MozillaOfficialAuthorization()
        serializer = Serializer(formats=['json', 'jsonp', 'xml'])
        paginator_class = Paginator
        cache_control = {'max-age': 0}
        list_allowed_methods = ['get']
        detail_allowed_methods = ['get']
        resource_name = 'users'
        restrict_fields = False
        restricted_fields = ['email', 'is_vouched']
        fields = []

    def build_filters(self, filters=None):
        es_filters = []
        for item in set(['email', 'country', 'region', 'city', 'ircname',
                         'username', 'languages', 'skills', 'groups',
                         'is_vouched', 'name']) & set(filters):
            es_filters.append(F(**{item: unquote(filters[item]).lower()}))

        return es_filters

    def dehydrate(self, bundle):
        if (bundle.request.GET.get('restricted', False)
            or not bundle.data['allows_mozilla_sites']):
            data = {}
            for key in self._meta.restricted_fields:
                data[key] = bundle.data[key]
            bundle = Bundle(obj=bundle.obj, data=data, request=bundle.request)

        return bundle

    def dehydrate_groups(self, bundle):
        return [unicode(g) for g in bundle.obj.groups.all()]

    def dehydrate_skills(self, bundle):
        return [unicode(g) for g in bundle.obj.skills.all()]

    def dehydrate_languages(self, bundle):
        return [unicode(g) for g in bundle.obj.languages.all()]

    def dehydrate_photo(self, bundle):
        if bundle.obj.photo:
            return urljoin(settings.SITE_URL, bundle.obj.photo.url)
        return ''

    def get_detail(self, request, **kwargs):
        if request.GET.get('restricted', False):
            raise ImmediateHttpResponse(response=http.HttpForbidden())

        return super(UserResource, self).get_detail(request, **kwargs)

    def apply_filters(self, request, applicable_filters):
        """Implement advanced filters.

        - Implement 'groups' filter.
        - Implement 'languages' filter.
        - Implement 'skills' filter.

        """
        if (request.GET.get('restricted', False)
            and 'email__text' not in applicable_filters
            and len(applicable_filters) != 1):
            raise ImmediateHttpResponse(response=http.HttpForbidden())

        if request.GET.get('restricted', False):
            applicable_filters.append(F(allows_community_sites=True))

        mega_filter = F()
        for filter in applicable_filters:
            mega_filter &= filter

        return S(UserProfile).filter(mega_filter)

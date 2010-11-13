from django.contrib.gis.db import models
from django.contrib.auth.models import User
from main.helpers import ApplicationError
from django.conf import settings
from django.contrib.gis.geos import Polygon
if settings.HISTORY_SUPPORT:
    import fullhistory
    from fullhistory.models import HistoryField
    history_support = True
else:
    history_support = False
    HistoryField = models.BooleanField

class License(models.Model):
    name = models.CharField(max_length=255)
    noncommercial = models.BooleanField(default=False)
    attribution = models.BooleanField(default=False)
    sharealike = models.BooleanField(default=False)
    additional = models.TextField()
    url = models.CharField(max_length=255, blank=True, null=True)
    flaglist = ['noncommercial', 'attribution', 'sharealike']
    history = HistoryField()
    def from_json(self, data):
        errors = []
        for key in ['name', 'url', 'restrictions', 'url']:
            setattr(self, key, data.get(key, ''))
        flags = data.get('options', {})
        for flag,value in flags.items():
            if flag not in self.flaglist:
                errors.append("Flag %s not supported: only supports %s" % (flag, ",".join(self.flaglist)))
            if value == True: 
                setattr(self, flag, True)
            else:
                setattr(self, flag, False)
        return self
    def to_json(self):
        flags = {}
        for key in self.flaglist:
            if getattr(self, key) == True:
                flags[key] = True
            else:
                flags[key] = False

        return {
            'id': self.id,
            'name': self.name,
            'additional': self.additional,
            'url': self.url,
            'options': flags
        }    

class Attribution(models.Model):
    attribution = models.TextField()

class Layer(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()
    owner = models.ForeignKey(User)
    date = models.DateTimeField(blank=True, null=True)
    attribution = models.ForeignKey(Attribution)
    def from_json(self, data):
        self.name = data['name']
        self.description = data['description']
        self.owner = User.objects.get(pk=data['user'])
        self.save()
        return self

    def to_json(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'owner': self.owner.id,
            'attribution': self.attribution.to_json(),
            'images': [i.to_json() for i in self.image_set.all()]
        }    

class WMS(models.Model):
    url = models.TextField()
    layer = models.CharField(max_length=255)
    attribution = models.ForeignKey(Attribution)
    owner = models.ForeignKey(User)
    capabilities = models.TextField(blank=True, null=True)
    capabilities_date = models.DateTimeField(blank=True, null=True)
    def from_json(self, data, user):
        required_keys = ['url', 'layer']
        optional_keys = ['capabilities']
        errors = []
        warnings = []
        for key in required_keys:
            if key in data:
                setattr(self, key, data[key])
            elif getattr(self, key) == None:
                errors.append("No %s provided for WMS." % key)
        for key in optional_keys:
            if key in data:
                setattr(self, key, data[key])
            else:
                warnings.append("Missing %s in image data. This is a recommended field." % key)
        if errors:
            raise ApplicationError(errors)
        self.owner = user
        self.capabilities_date = None
        self.save()
        return self

    def to_json(self):
        return {
            'id': self.id,
            'url': self.url,
            'layer': self.layer,
            'user': self.owner.id,
        }

class Image(models.Model):
    url = models.TextField()
    layer = models.ForeignKey(Layer, blank=True, null=True)
    file_size = models.IntegerField(blank=True,null=True)
    file_format = models.CharField(max_length=255, blank=True,null=True)
    crs = models.TextField(blank=True,null=True)
    bbox = models.PolygonField()
    width = models.IntegerField()
    height = models.IntegerField()
    hash = models.CharField(max_length=100, blank=True, null=True)
    license = models.ForeignKey(License, blank=True, null=True)
    attribution = models.ForeignKey(Attribution, blank=True, null=True)
    vrt = models.TextField(blank=True, null=True)
    vrt_date = models.DateTimeField(blank=True,null=True)
    archive = models.BooleanField(default=True)
    owner = models.ForeignKey(User)
    history = HistoryField()
    def from_json(self, data, user):
        required_keys = ['url', 'width', 'height']
        optional_keys = ['file_size', 'file_format', 'hash', 'crs', 'vrt', 'archive']
        errors = []
        warnings = []
        for key in required_keys:
            if key in data and data[key] != getattr(self, key):
                setattr(self, key, data[key])
            elif getattr(self, key) == None:
                errors.append("No %s provided for image." % key)
        for key in optional_keys:
            if key in data and data[key] != getattr(self, key):
                setattr(self, key, data[key])
            else:
                warnings.append("Missing %s in image data. This is a recommended field." % key)
        if 'layer' in data:
            errors.append("No layer handling available at this time. Please upload images without a Layer identifier.")
        if 'bbox' in data:
            geom = Polygon.from_bbox(data['bbox'])
            self.bbox = geom
        elif not self.bbox:
            errors.append("No BBOX provided for image.")
        if not 'license' in data and not self.license:
            errors.append("No license ID was passed")
        elif 'license' in data and isinstance(data['license'], int):
            self.license = License.objects.get(pk=data['license'])
        elif 'license' in data and isinstance(data['license'], dict):
             l = License()
             l.from_json(data['license'])
             l.save()
             self.license = l
        elif not self.license:
            errors.append("Some license information is required.")
        if errors:
            raise ApplicationError(errors)
        self.vrt_date = None
        self.owner = user
        return self
    def to_json(self):
        return {
            'id': self.id,
            'url': self.url,
            'file_size': self.file_size,
            'file_format': self.file_format,
            'crs': self.crs,
            'bbox': list(self.bbox.extent),
            'width': self.width,
            'height': self.height,
            'hash': self.hash,
            'archive': self.archive,
            'license': self.license.to_json(),
            'vrt': self.vrt,
            'vrt_date': self.vrt_date,
            'user': self.owner.id
        }    


if history_support:
    fullhistory.register_model(Image)        
    fullhistory.register_model(License)        

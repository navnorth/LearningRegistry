from copy import deepcopy
from jsonschema import validate, Draft3Validator, ValidationError
from lr.schema.validate import LRDraft3Validator
from lr.lib import helpers, SpecValidationException
from pylons import config
from uuid import uuid4


import couchdb, logging

log = logging.getLogger(__name__)

appConfig = config['app_conf']

#Default couchdb server that use by all the models when none is provided.
_defaultCouchServer =  couchdb.Server(appConfig['couchdb.url.dbadmin']) 

_ID = "_id"
_REV = "_rev"
_DOC_ID = "doc_ID"

def _createDB(name, server=_defaultCouchServer):
    try:
        server.create(name)
    except Exception as ex:
        pass
    return server[name]


class SchemaBackedModelHelper():
    validator_class = LRDraft3Validator

    def __init__(self, schemaRef, defaultDBName, server=_defaultCouchServer):
        self.schema = { "$ref": schemaRef }
        self.defaultDB = _createDB(defaultDBName, server)

    def validate_model(self, model):
        #strip couchdb specific stuff before validation
        if _ID in model or _REV in model:
            model_ref = deepcopy(model)
            try:
                del model_ref[_ID]
            except:
                pass

            try:
                del model_ref[_REV]
            except:
                pass
        else:
            model_ref = model

        try:
            validate(model_ref, self.schema, cls=self.validator_class)
        except ValidationError as ve:
            msgs = []
            for err in self.validator_class(self.schema).iter_errors(model_ref):
                msgs.append(err.message)

            raise SpecValidationException(",\n".join(msgs))

    def save(self,  model, database=None, log_exceptions=True):
            
            # Make sure the spec data conforms to the spec before saving
            # it to the database
            self.validate_model(model)
                
            db = database
            # If no database is provided use the default one.
            if db == None:
                db = self.defaultDB
            
            result = {'OK':True}   
            
            try:
                _id, _rev = db.save(model)
                
                if _ID not in model:
                    model[_ID] = _id

                if _REV not in model:
                    model[_REV] = _rev
                
            except Exception as e:
                result['OK'] = False
                result['ERROR'] = "CouchDB save error:  "+str(e)
                if log_exceptions:
                    log.exception("\n"+pprint.pformat(result, indent=4)+"\n"+
                          pprint.pformat(document, indent=4)+"\n\n")
                        
            return result


_db_resource_data = appConfig['couchdb.db.resourcedata']

_schemaRef_Resource_Data = appConfig['schema.resource_data']


class ResourceDataHelper(SchemaBackedModelHelper):
    DOC_ID = _DOC_ID
    TIME_STAMPS = ['create_timestamp', 'update_timestamp', 'node_timestamp']
    REPLICATION_FILTER = "filtered-replication/replication_filter"

    def set_timestamps(self, model, timestamp=helpers.nowToISO8601Zformat()):
        for stamp in ResourceDataHelper.TIME_STAMPS:
                model[stamp] = timestamp
        return model

    def save(self, model, database=None, log_exceptions=True):
        if _DOC_ID not in model:
            model[_DOC_ID] = uuid4().hex

        if _ID not in model:
            model[_ID] = model[_DOC_ID]

        return SchemaBackedModelHelper.save(self, model, database, log_exceptions)

ResourceDataModelValidator = ResourceDataHelper(_schemaRef_Resource_Data, _db_resource_data, _defaultCouchServer)





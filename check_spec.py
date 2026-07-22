from pyiceberg.catalog import load_catalog
catalog = load_catalog('lakehouse', uri='http://localhost:8181', **{
    's3.endpoint': 'http://localhost:9000',
    's3.access-key-id': 'admin',
    's3.secret-access-key': 'password123',
    's3.path-style-access': 'true',
    'downcast-ns-timestamp-to-us-on-write': 'true',
})
table = catalog.load_table('sales_db.sales')
print(table.spec())

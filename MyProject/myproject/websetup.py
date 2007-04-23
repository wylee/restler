import paste.deploy
import sqlalchemy
import myproject.models as model


def setup_config(command, filename, section, vars):
    """
    Place any commands to setup myproject here.
    """
    conf = paste.deploy.appconfig('config:' + filename)
    conf.update(dict(app_conf=conf.local_conf, global_conf=conf.global_conf))
    paste.deploy.CONFIG.push_process_config(conf)
    engine = sqlalchemy.create_engine(conf['sqlalchemy.dburi'])
    engine.echo = True
    model.metadata.connect(engine)
    drop_all_tables()
    create_all_tables()

def drop_all_tables():
    really_drop = raw_input('Really drop all tables?! [yes/N] ')
    if really_drop.lower().strip() == 'yes':
        print 'Dropping all tables...'
        model.metadata.drop_all()
    else:
        print 'Tables not dropped'

def create_all_tables():
    print 'Creating all tables...'
    model.metadata.create_all()
    print 'Done creating all tables.'

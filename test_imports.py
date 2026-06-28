import sys
sys.path.insert(0, r"D:\DeepScribe")
try:
    import novel_translator.services.gnuboard_db as db
    print("gnuboard_db file path:", db.__file__)
    print("Does GnuboardDB exist in db?", hasattr(db, "GnuboardDB"))
    if hasattr(db, "GnuboardDB"):
        print("GnuboardDB class definition module:", db.GnuboardDB.__module__)
except Exception as e:
    import traceback
    traceback.print_exc()

from django.contrib.staticfiles.storage import ManifestStaticFilesStorage

class CssOnlyManifestStaticFilesStorage(ManifestStaticFilesStorage):
    manifest_strict = False
    patterns = (
        ("*.css", (
            r"(?P<matched>url\(\s*(?P<quote>['\"])?(?P<url>[^)\"']+?)(?P=quote)?\s*\))",
            r"(?P<matched>@import\s*(?P<quote>['\"])(?P<url>.*?)(?P=quote))",
        )),
    )
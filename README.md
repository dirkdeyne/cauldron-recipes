# 🫕Cauldron's recipe book

Note: Works together with https://github.com/kevindeyne/cauldron

## Recipe format

Tool versions are defined in JSON files in the recipes repository:

```
/java/corretto.json
/java/adoptium.json
/maven/maven.json
...
```

Each file contains a list of versions with download URLs and checksums:

```json
[
  {
    "version": "21",
    "url": "https://corretto.aws/downloads/latest/amazon-corretto-21-x64-windows-jdk.zip",
    "checksums": {
      "SHA-256": "abc123..."
    }
  }
]
```

Each tool folder also contains a `_setup.json` that tells Cauldron which environment variable to set and where the binaries live:

```json
{
  "home_var": "JAVA_HOME",
  "bin_subdir": "bin"
}
```

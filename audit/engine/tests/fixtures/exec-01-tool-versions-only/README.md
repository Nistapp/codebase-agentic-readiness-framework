# exec-01-tool-versions-only

A Ruby, a .NET and a Maven project in one folder. No `.ruby-version`, `global.json` or `mvnw` exists. One shared
`.tool-versions` pins all three toolchains, with a `ruby`, a `dotnet` and a `java` line.

## Development

```bash
bundle install
dotnet build
mvn package
```

# Maven examples

## settings.xml (servers + optional mirror)

```xml

<settings>
    <servers>
        <server>
            <id>nexus-releases</id>
            <username>YOUR_USER</username>
            <password>YOUR_PASS</password>
        </server>
        <server>
            <id>nexus-snapshots</id>
            <username>YOUR_USER</username>
            <password>YOUR_PASS</password>
        </server>
    </servers>
    <!-- Optional global mirror (if using a single customer) -->
    <!--
    <mirrors>
      <mirror>
        <id>nexus-public</id>
        <mirrorOf>*</mirrorOf>
        <url>https://<REPO_ROUTE_HOST>/repository/maven-public/</url>
      </mirror>
    </mirrors>
    -->
</settings>

<distributionManagement>
<repository>
    <id>nexus-releases</id>
    <url>https://<REPO_ROUTE_HOST>/repository/maven-releases/
    </url>
</repository>
<snapshotRepository>
    <id>nexus-snapshots</id>
    <url>https://<REPO_ROUTE_HOST>/repository/maven-snapshots/
    </url>
</snapshotRepository>
</distributionManagement>
```

```bash
mvn -DaltReleaseDeploymentRepository=nexus-releases::default::https://<REPO_ROUTE_HOST>/repository/maven-releases/ \
    -DaltSnapshotDeploymentRepository=nexus-snapshots::default::https://<REPO_ROUTE_HOST>/repository/maven-snapshots/ \
    -DskipTests deploy
```

# Stage 1: build with Maven
FROM maven:3.9-eclipse-temurin-21 AS build
WORKDIR /src
COPY pom.xml .
RUN mvn -q -B dependency:go-offline
COPY src src
RUN mvn -q -B package

# Stage 2: small runtime image with only the JRE and the jar
FROM eclipse-temurin:21-jre
ARG VERSION=dev
ENV VERSION=${VERSION}
WORKDIR /app
COPY --from=build /src/target/app.jar app.jar
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "app.jar"]
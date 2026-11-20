# ============================================================

# Stage 1: Build

# ============================================================

FROM eclipse-temurin:21-jdk-jammy AS builder
WORKDIR /build


# Copy Maven wrapper and POM first (layer-cache friendly)
COPY hospitalnode/mvnw hospitalnode/mvnw.cmd ./
COPY hospitalnode/.mvn ./.mvn
RUN chmod +x mvnw


COPY hospitalnode/pom.xml ./hospitalnode/
RUN ./mvnw dependency:resolve -f hospitalnode/pom.xml -B


COPY hospitalnode/src ./hospitalnode/src
RUN ./mvnw clean package -f hospitalnode/pom.xml -DskipTests -B


# ============================================================
# Stage 2: Runtime
# ============================================================

FROM eclipse-temurin:21-jre-jammy AS runtime

WORKDIR /app
# Copy the fat jar from the build stage
COPY --from=builder /build/hospitalnode/target/hospitalnode-*.jar hospitalnode.jar
# Non-root user for security
#RUN addgroup --system sermon && adduser --system --ingroup sermon sermon
#USER sermon

EXPOSE 9000
ENTRYPOINT ["java", "-jar", "hospitalnode.jar"]
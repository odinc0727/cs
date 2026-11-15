FROM golang:1.23-alpine AS build
WORKDIR /src
COPY go.mod ./
RUN go mod download
COPY main.go ./
RUN CGO_ENABLED=0 go build -mod=mod -o /service .
FROM alpine:3.21
COPY --from=build /service /service
ENTRYPOINT ["/service"]

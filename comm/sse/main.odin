package main

import "core:fmt"
import "core:net"
import "core:strings"
import "core:thread"
import "core:time"

main :: proc() {
	listener, err := net.listen_tcp(net.Endpoint{address = net.IP4_Loopback, port = 8080})
	if err != nil {
		fmt.printfln("Failed to listen {}", err)
		return
	}
	defer net.close(listener)

	fmt.println("SSE server: http://127.0.0.1:8080/events")

	for {
		client, _, accept_err := net.accept_tcp(listener)
		if accept_err != nil {
			continue
		}

		thread.create_and_start_with_poly_data(client, handle_client)
	}
}

handle_client :: proc(sock: net.TCP_Socket) {
	defer net.close(sock)

	request_buf: [4096]u8
	n, err := net.recv_tcp(sock, request_buf[:])
	if err != nil || n == 0 {
		return
	}

	request := string(request_buf[:])
	if !strings.has_prefix(request, "GET /events") {
		send_text(sock, "HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\nConnection: close\r\n")
		return
	}

	// SSE 响应头
	headers :=
		"HTTP/1.1 200 OK\r\n" +
		"Content-Type: text/event-stream; charset=utf-8\r\n" +
		"Cache-Control: no-cache\r\n" +
		"Connection: close\r\n" +
		"Access-Control-Allow-Origin: *\r\n" +
		"X-Accel-Buffering: no\r\n" +
		"\r\n"

	if !send_text(sock, headers) {
		return
	}

	fmt.println("SSE client connected")

	for i := 1;; i += 1 {
		buffer: [256]u8
		message := fmt.bprintf(
			buffer[:],
			"id: %d\nevent: tick\ndata: {\"count\":%d,\"message\":\"Hello from Odin\"}\n\n",
			i,
			i,
		)
		if !send_text(sock, message) {
			break
		}
		time.sleep(time.Second)
	}

	fmt.println("SSE client disconnected")
}

send_text :: proc(sock: net.TCP_Socket, text: string) -> bool {
	_, err := net.send_tcp(sock, transmute([]u8)text)
	return err == nil
}

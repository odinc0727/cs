package main

import "core:c"
import "core:crypto"
import "core:fmt"

// C ABI
Redis_Context :: struct {
	funcs: rawptr,
	err:   c.int,
}

Redis_Reply :: struct {
	kind:     c.int,
	integer:  c.longlong,
	dval:     c.double,
	len:      c.size_t,
	str:      cstring,
	vtype:    [4]c.char,
	elements: c.size_t,
	element:  ^^Redis_Reply,
}

foreign import hiredis "system:hiredis"

foreign hiredis {
	redisConnect :: proc(ip: cstring, port: c.int) -> ^Redis_Context ---
	redisFree :: proc(ctx: ^Redis_Context) ---
	redisCommandArgv :: proc(ctx: ^Redis_Context, argc: c.int, argv: ^cstring, argvlen: ^c.size_t) -> ^Redis_Reply ---
	freeReplyObject :: proc(reply: rawptr) ---
}

// 通过参数数组执行 Redis 命令
redis_command :: proc(ctx: ^Redis_Context, args: []string) -> ^Redis_Reply {
	assert(len(args) > 0 && len(args) <= 6)

	argv: [6]cstring
	lengths: [6]c.size_t

	for arg, i in args {
		argv[i] = cstring(raw_data(arg))
		lengths[i] = c.size_t(len(arg))
	}

	return redisCommandArgv(ctx, c.int(len(args)), &argv[0], &lengths[0])
}

Lock_Result :: enum {
	Acquired,
	Busy,
	Failed,
}

// SET key token NX PX 30000
try_lock :: proc(ctx: ^Redis_Context, key, token: string) -> Lock_Result {
	reply := redis_command(ctx, {"SET", key, token, "NX", "PX", "30000"})

	if reply == nil {
		return .Failed
	}
	defer freeReplyObject(rawptr(reply))

	switch reply.kind {
	case 5:
		// REDIS_REPLY_STATUS
		if string(reply.str) == "OK" {
			return .Acquired
		}

	case 4:
		// REDIS_REPLY_NIL
		return .Busy

	case 6:
		// REDIS_REPLY_ERROR
		fmt.println("SET error:", string(reply.str))

	case:
	}

	return .Failed
}

Unlock_Result :: enum {
	Released,
	Not_Owner,
	Failed,
}

// 解锁需要校验身份，需要 Lua 脚本保持原子性
UNLOCK_SCRIPT :: "if redis.call('GET', KEYS[1]) == ARGV[1] then return redis.call('DEL', KEYS[1]) else return 0 end"

// 原子校验 token 并删除锁
unlock :: proc(ctx: ^Redis_Context, key, token: string) -> Unlock_Result {
	reply := redis_command(ctx, {"EVAL", UNLOCK_SCRIPT, "1", key, token})
	if reply == nil {
		return .Failed
	}
	defer freeReplyObject(rawptr(reply))

	if reply.kind == 6 {
		fmt.println("EVAL error:", string(reply.str))
		return .Failed
	}
	if reply.kind != 3 { 	// REDIS_REPLY_INTEGER
		return .Failed
	}
	if reply.integer == 1 {
		return .Released
	}

	return .Not_Owner
}

main :: proc() {
	ctx := redisConnect("127.0.0.1", 6379)
	if ctx == nil {
		fmt.println("Redis connection allocation failed")
		return
	}
	defer redisFree(ctx)

	if ctx.err != 0 {
		fmt.println("Redis connection failed:", ctx.err)
		return
	}

	// 为每次加锁生成 128-bit 随机 token
	entropy: [16]u8
	crypto.rand_bytes(entropy[:])

	digits := "0123456789abcdef"
	token_buffer: [32]u8
	for b, i in entropy {
		token_buffer[i * 2] = digits[int(b >> 4)]
		token_buffer[i * 2 + 1] = digits[int(b & 0x0f)]
	}

	token := string(token_buffer[:])
	key := "lock:order:1001"

	result := try_lock(ctx, key, token)
	if result != .Acquired {
		fmt.println("Acquire lock:", result)
		return
	}

	fmt.println("Lock acquired")

	// 离开作用域时安全解锁
	defer {
		result := unlock(ctx, key, token)
		fmt.println("Unlock:", result)
	}

	// 需要加锁的业务逻辑
	fmt.println("Processing order 1001...")
}

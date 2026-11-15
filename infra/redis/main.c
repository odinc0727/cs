#include <hiredis/hiredis.h>
#include <hiredis/read.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/time.h>

int main() {
        struct timeval timeout = {.tv_sec = 2, .tv_usec = 0};

        redisContext* ctx = redisConnectWithTimeout("127.0.0.1", 6379, timeout);
        if (ctx == NULL) {
                fprintf(stderr, "fail to connect redis...\n");
                return 1;
        }
        if (ctx->err) {
                fprintf(stderr, "fail to connect redis: %s\n", ctx->errstr);
                goto freeCtx;
                return 1;
        }

        // 写入 String，60 秒后过期
        redisReply* reply = redisCommand(ctx, "SET %s %s EX 60", "demo:hello", "Hello from Redis");
        if (reply == NULL || reply->type == REDIS_REPLY_ERROR) {
                fprintf(stderr, "SET failed: %s\n", reply ? reply->str : ctx->errstr);
                goto reply;
                return 1;
        }

        printf("SET: %s\n", reply->str);
        freeReplyObject(reply);

        // 读取 String
        reply = redisCommand(ctx, "GET %s", "demo:hello");
        if (reply == NULL) {
                fprintf(stderr, "GET failed: %s\n", ctx->errstr);
        } else if (reply->type == REDIS_REPLY_STRING) {
                printf("GET: %s\n", reply->str);
        } else if (reply->type == REDIS_REPLY_NIL) {
                printf("Key not exists...\n");
        } else if (reply->type == REDIS_REPLY_ERROR) {
                fprintf(stderr, "GET failed: %s\n", reply->str);
        }

reply:
        freeReplyObject(reply);
freeCtx:
        redisFree(ctx);

        return 0;
}

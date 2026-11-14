import redis


def bloom_demo(r: redis.Redis) -> None:
        print("=== Bloom Filter ===")

        key = "demo:bf"
        bf = r.bf()

        # 初始化：误判率 0.1%，预计容量 1000
        bf.reserve(key, 0.001, 1000)

        # 添加元素
        print("ADD apple:", bf.add(key, "apple"))
        print("ADD apple again:", bf.add(key, "apple"))  # 可能已经存在，没有新增记录

        # 批量添加
        print("MADD:", bf.madd(key, "banana", "orange"))

        # 查询
        print("EXISTS apple:", bf.exists(key, "apple"))
        print("EXISTS grape:", bf.exists(key, "grape"))

        # 批量查询
        print("MEXISTS:", bf.mexists(key, "apple", "banana", "grape"))

        # 统计与信息
        print("CARD:", bf.card(key))
        print("INFO:", bf.info(key))


def cuckoo_demo(r: redis.Redis) -> None:
        print("\n=== Cuckoo Filter ===")

        key = "demo:cf"
        cf = r.cf()

        # 初始化：预计容量 1000
        cf.reserve(key, 1000)

        # 添加元素
        print("ADD apple:", cf.add(key, "apple"))

        # 只在判断为不存在时添加
        print("ADDNX apple:", cf.addnx(key, "apple"))

        # 批量添加
        print("INSERT:", cf.insert(key, ["banana", "orange"]))

        # 查询
        print("EXISTS apple:", cf.exists(key, "apple"))
        print("EXISTS grape:", cf.exists(key, "grape"))

        # 批量查询
        print("MEXISTS:", cf.mexists(key, "apple", "banana", "grape"))

        # 重复添加
        print("ADD banana again:", cf.add(key, "banana"))
        print("COUNT banana:", cf.count(key, "banana"))

        # 删除一个匹配项
        # 由于指纹碰撞，不要对没有确认插入成功的元素随意执行删除
        print("DEL banana:", cf.delete(key, "banana"))
        print("COUNT banana:", cf.count(key, "banana"))

        # 删除 apple
        print("DEL apple:", cf.delete(key, "apple"))
        print("EXISTS apple:", cf.exists(key, "apple"))

        # 统计信息
        print("INFO:", cf.info(key))


if __name__ == "__main__":
        with redis.Redis(host="127.0.0.1", port=6379, db=0) as r:
                r.ping()

                # 仅清理演示数据，保证可以重复运行
                r.delete("demo:bf", "demo:cf")

                bloom_demo(r)
                cuckoo_demo(r)

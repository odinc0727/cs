package main

import (
	"fmt"
	"log"
	"net/http"
	_ "net/http/pprof"
	"sync"
)

// sync.Mutex 和 sync.RWMutex 都是不可重入
// - sync.Mutex 不跟踪锁的 Goroutine 持有者
// - Go 不提供 Goroutine ID 的官方获取接口，无法进程线程的身份识别

type Counter struct {
	mu sync.Mutex
	n  int
}

func (c *Counter) Add(n int) {
	c.mu.Lock()
	defer c.mu.Unlock()

	c.n += n
}

func (c *Counter) AddTwice(n int) {
	c.mu.Lock()
	defer c.mu.Unlock()

	c.Add(n) // 死锁
	c.Add(n)
}

func (c *Counter) NewAdd(n int) {
	c.mu.Lock()
	defer c.mu.Unlock()

	c.n += n
}

func (c *Counter) NewAddTwice(n int) {
	c.NewAdd(n)
	c.NewAdd(n)
}

func main() {
	go func() {
		log.Println("pprof: http://127.0.0.1:6060/debug/pprof")
		log.Println(http.ListenAndServe("127.0.0.1:6060", nil))
	}()

	counter := &Counter{}

	// counter.Add(10)
	// fmt.Println("Before: ", counter.n)
	// counter.AddTwice(5)               // 死锁
	// fmt.Println("After: ", counter.n) // 不会执行

	counter.Add(10)
	fmt.Println("Before: ", counter.n)
	counter.NewAddTwice(5)
	fmt.Println("After: ", counter.n)
}

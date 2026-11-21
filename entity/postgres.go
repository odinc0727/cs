package main

import (
	"context"
	"fmt"
	"os/exec"
	"strings"
	"time"
)

type postgresStore struct{}

func (postgresStore) Find(ctx context.Context, uid string) (string, error) {
	ctx, cancel := context.WithTimeout(ctx, 2*time.Second)
	defer cancel()

	// A real PostgreSQL query over a single inline row.
	const query = `
SELECT value
FROM (VALUES (:'demo_uid'::uuid, 'hello from PostgreSQL')) AS demo(uid, value)
WHERE uid = :'uid'::uuid;
`
	cmd := exec.CommandContext(ctx, "psql",
		"-X",
		"-w",
		"-Atq",
		"-v", "ON_ERROR_STOP=1",
		"-v", "uid="+uid,
		"-v", "demo_uid="+demoUID,
	)
	cmd.Stdin = strings.NewReader(query)
	out, err := cmd.CombinedOutput()
	if err != nil {
		return "", fmt.Errorf("postgres select: %w (%s)", err, strings.TrimSpace(string(out)))
	}
	value := strings.TrimSpace(string(out))
	if value == "" {
		return "", errNotFound
	}
	return value, nil
}

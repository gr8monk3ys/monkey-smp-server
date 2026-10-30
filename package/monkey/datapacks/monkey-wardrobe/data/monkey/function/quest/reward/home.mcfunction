# The bed advancement fired: the step's score, which the check picks up within a second. Taken back so a
# world whose quest restarts (a test server) can fire it again; the score keeps it from firing twice.
scoreboard players set @s rq.home 1
advancement revoke @s only monkey:quest/home

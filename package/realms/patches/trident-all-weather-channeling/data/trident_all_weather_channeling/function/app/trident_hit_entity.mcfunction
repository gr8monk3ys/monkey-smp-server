advancement revoke @a only trident_all_weather_channeling:trident_hit_entity

execute as @e[type=trident,nbt={DealtDamage:1b,inGround:0b},sort=nearest,limit=1] \
  if entity @s[nbt={item:{components:{"minecraft:enchantments":{"minecraft:channeling":1}}}}] \
    run function trident_all_weather_channeling:app/summon_lightning
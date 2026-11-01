import * as THREE from 'three';
import { loadGLTF, loadPixelTexture } from '../engine/assets.js';
import { addLighting, prepareLevel } from '../engine/world.js';
import { PokemonSprite, SheetSprite } from '../engine/sprites.js';
import { Particles } from '../engine/particles.js';
import { animate, wait, easeOut } from '../engine/tween.js';
import { playMusic, sounds } from '../engine/audio.js';
import { BattleHud } from '../ui/battleHud.js';
import { useMove, resetStages, expReward, gainExp, STAT_NAMES } from '../game/pokemon.js';
import { ITEMS, itemIcon, useHealItem, captureRoll } from '../game/items.js';
import { firstAlive, storeCaught } from '../game/state.js';

const LEVEL = '/assets/scenes/battle-forest.glb';
const PIXEL_SCALE = 0.03; // mètres par pixel de sprite
const STAT_ARTICLE = { atk: "L'", def: 'La ', spa: "L'", spd: 'La ', spe: 'La ', acc: 'La ', eva: "L'" };
const TRAINER_EXP_BONUS = 1.5;

/**
 * Combat dans la clairière exportée de Blender, contre un Pokémon sauvage (enemyTeam d'un
 * seul Pokémon, trainer = null) ou un dresseur (son équipe complète).
 * onEnd(issue) est appelé à la fin : 'win', 'lose', 'run' ou 'caught'.
 */
export async function createBattle({ hud: container, state, enemyTeam, trainer = null, onEnd }) {
  const gltf = await loadGLTF(LEVEL);
  const level = gltf.scene;
  prepareLevel(level);
  const scene = new THREE.Scene();
  scene.add(level);
  level.updateMatrixWorld(true);

  const center = new THREE.Vector3(0, 0, -8);
  const { sun } = await addLighting(scene, { shadowExtent: 34 });
  // Soleil haut à gauche, légèrement côté caméra : feuillages éclairés, ombres en travers.
  sun.position.copy(center).add(new THREE.Vector3(-26, 28, 10));
  sun.target.position.copy(center);

  const source = gltf.cameras[0];
  const camera = new THREE.PerspectiveCamera(source.fov, 16 / 9, 0.1, 300);
  source.getWorldPosition(camera.position);
  source.getWorldQuaternion(camera.quaternion);
  const cameraBase = camera.position.clone();

  const spawnOf = (name) => level.getObjectByName(name).getWorldPosition(new THREE.Vector3());
  const spawn = { player: spawnOf('Spawn_PlayerPokemon'), enemy: spawnOf('Spawn_EnemyPokemon') };
  const sprites = { player: null, enemy: null, trainer: null };

  const particles = new Particles(scene);
  const hud = new BattleHud(container);
  let active = firstAlive(state.party);
  let enemyIndex = 0;
  const mon = (side) => (side === 'player' ? state.party[active] : enemyTeam[enemyIndex]);
  const other = (side) => (side === 'player' ? 'enemy' : 'player');
  const name = (side) => mon(side).species.name.fr;
  const nameOf = (side) => (side === 'player' ? name(side) : `${name(side)} ${trainer ? 'ennemi' : 'sauvage'}`);
  const trainerName = trainer ? `${trainer.title} ${trainer.name}` : '';
  const chest = (sprite) => sprite.position.clone().add(new THREE.Vector3(0, sprite.size.y * 0.5, 0));

  for (const m of [...state.party, ...enemyTeam]) resetStages(m);
  hud.setParty(state.party);
  hud.setEnemyParty(trainer ? enemyTeam : null);
  hud.showPanel('player', false);
  hud.showPanel('enemy', false);
  playMusic('battle');

  // ------------------------------------------------------------ mises en scène

  async function sendOut(side) {
    const old = sprites[side];
    if (old) {
      scene.remove(old);
      old.dispose();
    }
    const m = mon(side);
    const sprite = await PokemonSprite.create(m.species.id, side === 'player' ? 'back' : 'front',
      side === 'player' ? PIXEL_SCALE * 1.15 : PIXEL_SCALE);
    sprite.position.copy(spawn[side]);
    sprite.scale.setScalar(0.001);
    scene.add(sprite);
    sprites[side] = sprite;
    resetStages(m);
    hud.setMon(side, m);
    hud.showPanel(side, true);
    particles.burst(chest(sprite).setY(spawn[side].y + 0.6), 'normal', { count: 10, spread: 1.2 });
    sounds.cry(m.species.id);
    await animate(350, (t) => sprite.scale.setScalar(easeOut(t)));
  }

  async function withdraw(side) {
    const sprite = sprites[side];
    await animate(250, (t) => sprite.scale.setScalar(1 - t));
    sprite.visible = false;
  }

  async function lunge(sprite, target) {
    const start = sprite.position.clone();
    const dir = target.position.clone().sub(start).setY(0).normalize().multiplyScalar(1.1);
    await animate(320, (t) => sprite.position.copy(start).addScaledVector(dir, Math.sin(t * Math.PI)));
  }

  async function blink(sprite) {
    for (let i = 0; i < 4; i++) {
      sprite.visible = !sprite.visible;
      await wait(80);
    }
    sprite.visible = true;
  }

  async function faint(side) {
    const sprite = sprites[side];
    sounds.cry(mon(side).species.id);
    await animate(450, (t) => { sprite.scale.y = 1 - easeOut(t); });
    sprite.visible = false;
    hud.showPanel(side, false);
    await hud.say(`${nameOf(side)} est K.O. !`, 1200);
  }

  /** Lancer de Ball : la Ball vole, aspire le Pokémon, tremble, puis le garde ou le relâche. */
  async function throwBall(key) {
    const target = sprites.enemy;
    const ball = new THREE.Sprite(new THREE.SpriteMaterial({ map: await loadPixelTexture(itemIcon(key)) }));
    ball.scale.setScalar(0.5);
    scene.add(ball);
    const from = chest(sprites.player).add(new THREE.Vector3(0, 0.8, 0));
    const to = chest(target);
    await hud.say(`Vous lancez une ${ITEMS[key].name} !`, 300);
    await animate(650, (t) => {
      ball.position.lerpVectors(from, to, t);
      ball.position.y += Math.sin(t * Math.PI) * 2.5;
      ball.material.rotation = -t * 12;
    });
    particles.burst(to, 'fire', { count: 10, spread: 0.8, life: 0.5 });
    await animate(300, (t) => target.scale.setScalar(1 - t));
    target.visible = false;
    const ground = spawn.enemy.y + 0.25;
    await animate(250, (t) => { ball.position.y = to.y + (ground - to.y) * t * t; });

    const { shakes, caught } = captureRoll(mon('enemy'), ITEMS[key].rate);
    for (let i = 0; i < shakes; i++) {
      await wait(450);
      await animate(320, (t) => { ball.material.rotation = Math.sin(t * Math.PI * 2) * 0.5; });
    }
    await wait(500);
    if (caught) {
      particles.burst(ball.position.clone(), 'electric', { count: 16, spread: 1 });
      await hud.say(`Et hop ! ${name('enemy')} est attrapé !`, 1500);
      const where = storeCaught(state, mon('enemy'));
      hud.setParty(state.party);
      await hud.say(where === 'party'
        ? `${name('enemy')} rejoint votre équipe !`
        : `Votre équipe est pleine : ${name('enemy')} est envoyé dans le PC.`, 1500);
      return true;
    }
    scene.remove(ball);
    ball.material.dispose();
    particles.burst(ball.position.clone(), 'normal', { count: 12, spread: 1.2 });
    target.visible = true;
    await animate(250, (t) => target.scale.setScalar(t));
    await hud.say(['Oh non ! Le Pokémon s\'est libéré !', 'Raah ! Ça y était presque !',
      'Aaaah ! Presque !', 'Mince ! Ça y était presque !'][shakes], 1300);
    return false;
  }

  async function perform(side, move) {
    const target = other(side);
    await hud.say(`${nameOf(side)} utilise ${move.name.fr} !`, 650);
    const result = useMove(mon(side), mon(target), move);
    if (result.missed) return hud.say(`${nameOf(side)} rate son attaque !`, 1000);

    const a = sprites[side];
    const d = sprites[target];
    if (move.category === 'physical') await lunge(a, d);
    else if (move.category === 'special') await particles.projectile(chest(a), chest(d), move.type);

    if (move.category !== 'status') {
      particles.burst(chest(d), move.type);
      sounds.hit();
      await blink(d);
      hud.setHp(target, mon(target));
      await wait(600);
      if (result.critical) await hud.say('Coup critique !', 800);
      if (result.effectiveness === 0) await hud.say(`Ça n'affecte pas ${nameOf(target)}…`, 1000);
      else if (result.effectiveness > 1) await hud.say("C'est super efficace !", 1000);
      else if (result.effectiveness < 1) await hud.say("Ce n'est pas très efficace…", 1000);
    }
    for (const { target: who, stat, change, blocked } of result.statChanges) {
      const whoSide = who === mon('player') ? 'player' : 'enemy';
      particles.burst(chest(sprites[whoSide]), change > 0 ? 'fairy' : 'ghost', { count: 8, spread: 0.8 });
      const verb = change > 0 ? (blocked ? 'ne peut plus monter' : 'monte') : (blocked ? 'ne peut plus baisser' : 'baisse');
      await hud.say(`${STAT_ARTICLE[stat]}${STAT_NAMES[stat]} de ${nameOf(whoSide)} ${verb} !`, 1000);
    }
    if (move.category === 'status' && !result.statChanges.length) await hud.say('Mais rien ne se passe…', 900);
  }

  async function giveExp(defeated) {
    const gain = Math.floor(expReward(defeated) * (trainer ? TRAINER_EXP_BONUS : 1));
    const m = mon('player');
    await hud.say(`${m.species.name.fr} gagne ${gain} points d'Exp. !`, 1100);
    for (const event of gainExp(m, gain)) {
      hud.setExp(m);
      await wait(900);
      if (event.level) {
        hud.setMon('player', m);
        await hud.say(`${m.species.name.fr} monte au N.${event.level} !`, 1300);
      } else {
        await hud.say(`${m.species.name.fr} apprend ${event.learned.name.fr} !`, 1300);
      }
    }
    hud.setExp(m);
    await wait(500);
  }

  async function showTrainer(visible) {
    const sprite = sprites.trainer;
    const x = spawn.enemy.x;
    sprite.visible = true;
    await animate(400, (t) => {
      const k = visible ? 1 - t : t;
      sprite.position.x = x + k * 3;
    });
    sprite.visible = visible;
  }

  /** Gère un K.O. ; renvoie l'issue du combat s'il est terminé, sinon null. */
  async function handleFaint(side) {
    await faint(side);
    if (side === 'enemy') {
      await giveExp(mon('enemy'));
      hud.setEnemyParty(trainer ? enemyTeam : null);
      const next = enemyTeam.findIndex((m) => m.hp > 0);
      if (next === -1) {
        if (!trainer) return 'win';
        state.money += trainer.reward;
        await showTrainer(true);
        await hud.say(`Vous avez battu ${trainerName} !`, 1300);
        await hud.say(`« ${trainer.defeat} »`, 2000);
        await hud.say(`Vous remportez ${trainer.reward} ₽ !`, 1300);
        return 'win';
      }
      enemyIndex = next;
      await hud.say(`${trainerName} envoie ${name('enemy')} !`, 900);
      await sendOut('enemy');
      return null;
    }
    hud.setParty(state.party);
    if (firstAlive(state.party) === -1) {
      await hud.say("Vous n'avez plus de Pokémon en état de se battre !", 1500);
      await hud.say('Vous vous précipitez vers l\'infirmière…', 1500);
      return 'lose';
    }
    active = await hud.choosePokemon(state.party, active);
    await hud.say(`En avant, ${name('player')} !`, 800);
    await sendOut('player');
    return null;
  }

  const pickMove = (m) => {
    const usable = m.moves.filter((move) => move.ppLeft > 0);
    return usable[Math.floor(Math.random() * usable.length)] ?? m.moves[0];
  };

  /** Action du joueur hors attaque. Renvoie 'caught' si la capture réussit, false si le tour n'est pas consommé. */
  async function playerAction(choice) {
    if (choice.action === 'switch') {
      await hud.say(`${name('player')}, reviens !`, 700);
      await withdraw('player');
      active = choice.index;
      await hud.say(`En avant, ${name('player')} !`, 700);
      await sendOut('player');
      return true;
    }
    const item = ITEMS[choice.key];
    if (item.kind === 'ball') {
      if (trainer) {
        await hud.say(`Vous lancez une ${item.name}…`, 700);
        await hud.say("Le Dresseur dévie la Ball ! Voler, c'est mal !", 1500);
        return false;
      }
      state.bag[choice.key] -= 1;
      return (await throwBall(choice.key)) ? 'caught' : true;
    }
    const healed = useHealItem(state.bag, choice.key, mon('player'));
    if (!healed) {
      await hud.say("Ça n'aura aucun effet.", 1000);
      return false;
    }
    await hud.say(`Vous utilisez une ${item.name}.`, 700);
    hud.setHp('player', mon('player'));
    await hud.say(`${name('player')} récupère ${healed} PV !`, 1100);
    return true;
  }

  async function run() {
    if (trainer) {
      const tex = await loadPixelTexture(`/assets/trainers/${trainer.sprite}.png`);
      sprites.trainer = new SheetSprite(tex, { frameW: 80, frameH: 80, cols: 1, rows: 1, pixelScale: PIXEL_SCALE });
      sprites.trainer.position.copy(spawn.enemy);
      scene.add(sprites.trainer);
      await hud.say(`${trainerName} veut se battre !`, 1600);
      await showTrainer(false);
      await hud.say(`${trainerName} envoie ${name('enemy')} !`, 600);
      await sendOut('enemy');
    } else {
      await sendOut('enemy');
      await hud.say(`Un ${name('enemy')} sauvage apparaît !`, 1400);
    }
    await sendOut('player');
    await hud.say(`En avant, ${name('player')} !`, 900);

    for (;;) {
      hud.message.textContent = `Que doit faire ${name('player')} ?`;
      const choice = await hud.chooseAction(mon('player'), { party: state.party, active, bag: state.bag });
      if (choice.action === 'run') {
        if (trainer) {
          await hud.say('Impossible de fuir un combat de Dresseur !', 1200);
          continue;
        }
        await hud.say('Vous prenez la fuite !', 1000);
        return 'run';
      }
      let playerMove = null;
      if (choice.action === 'move') {
        playerMove = choice.move;
      } else {
        const done = await playerAction(choice);
        if (done === 'caught') return 'caught';
        if (!done) continue;
      }

      // Objets et changements passent avant les attaques ; sinon priorité puis Vitesse.
      const theirs = pickMove(mon('enemy'));
      const playerFirst = playerMove && (playerMove.priority !== theirs.priority
        ? playerMove.priority > theirs.priority
        : mon('player').spe * (1 + Math.random() * 0.01) >= mon('enemy').spe);
      const order = !playerMove ? ['enemy'] : playerFirst ? ['player', 'enemy'] : ['enemy', 'player'];
      for (const side of order) {
        await perform(side, side === 'player' ? playerMove : theirs);
        const target = other(side);
        if (mon(target).hp > 0) continue;
        const outcome = await handleFaint(target);
        if (outcome) return outcome;
        break; // le remplaçant n'agit pas ce tour-ci
      }
    }
  }

  let time = 0;
  run().then(onEnd);

  return {
    scene,
    camera,
    enemyTeam, // accessible depuis la console (window.game.view) pour tester
    // Net des deux Pokémon (≈ 5 et 13 m de la caméra), forêt du fond adoucie.
    focus: { distance: 9, range: 5 },
    update(dt) {
      time += dt;
      camera.position.copy(cameraBase).add(new THREE.Vector3(Math.sin(time * 0.4) * 0.06, Math.sin(time * 0.6) * 0.03, 0));
      for (const sprite of Object.values(sprites)) {
        if (!sprite) continue;
        sprite.update?.(dt);
        sprite.faceCamera(camera);
      }
      particles.update(dt);
    },
    resize(aspect) {
      camera.aspect = aspect;
      camera.updateProjectionMatrix();
    },
    dispose() {
      hud.dispose();
      scene.remove(level);
      for (const sprite of Object.values(sprites)) sprite?.dispose();
    },
  };
}

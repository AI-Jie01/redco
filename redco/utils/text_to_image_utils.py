import numpy as np
import jax
import jax.numpy as jnp


def preprocess(image, resolution, dtype):
    image = image.convert('RGB').resize((resolution, resolution))
    image = np.array(image, dtype=dtype) / 255.0
    image = image.transpose(2, 0, 1)
    return image


def text_to_image_default_collate_fn(examples,
                                     pipeline,
                                     resolution,
                                     image_key='image',
                                     text_key='text'):
    batch = pipeline.tokenizer(
        [example[text_key] for example in examples],
        max_length=pipeline.tokenizer.model_max_length,
        padding='max_length',
        truncation=True,
        return_tensors='np')

    if image_key in examples[0]:
        batch['pixel_values'] = np.stack([
            preprocess(
                example[image_key], resolution=resolution, dtype=np.float32)
            for example in examples])

    return batch


def text_to_image_default_loss_fn(
        state, params, batch, train, pipeline, freezed_params):
    dropout_rng, sample_rng, noise_rng, timestep_rng = \
        jax.random.split(state.train_rng, num=4)

    # Convert images to latent space
    vae_outputs = pipeline.vae.apply(
        {"params": freezed_params['vae']}, batch["pixel_values"],
        deterministic=True, method=pipeline.vae.encode)
    latents = vae_outputs.latent_dist.sample(sample_rng)
    # (NHWC) -> (NCHW)
    latents = jnp.transpose(latents, (0, 3, 1, 2))
    latents = latents * 0.18215

    # Sample noise that we'll add to the latents
    noise_rng, timestep_rng = jax.random.split(sample_rng)
    noise = jax.random.normal(noise_rng, latents.shape)
    # Sample a random timestep for each image
    bsz = latents.shape[0]
    timesteps = jax.random.randint(
        key=timestep_rng,
        shape=(bsz,),
        minval=0,
        maxval=pipeline.scheduler.config.num_train_timesteps)

    # Add noise to the latents according to the noise magnitude at each timestep
    # (this is the forward diffusion process)
    noisy_latents = pipeline.scheduler.add_noise(
        original_samples=latents,
        noise=noise,
        timesteps=timesteps)

    # Get the text embedding for conditioning
    if 'text_encoder' in params:
        encoder_hidden_states = pipeline.text_encoder(
            batch["input_ids"],
            params=params["text_encoder"],
            dropout_rng=dropout_rng,
            train=train)[0]
    else:
        encoder_hidden_states = pipeline.text_encoder(
            batch["input_ids"],
            params=freezed_params['text_encoder'],
            train=False)[0]

    # Predict the noise residual
    unet_outputs = pipeline.unet.apply(
        {"params": params["unet"]},
        sample=noisy_latents,
        timesteps=timesteps,
        encoder_hidden_states=encoder_hidden_states,
        train=train)
    noise_pred = unet_outputs.sample

    return jnp.mean(jnp.square(noise - noise_pred))


def text_to_image_default_pred_fn(pred_rng,
                                  batch,
                                  params,
                                  pipeline,
                                  freezed_params,
                                  n_infer_steps,
                                  resolution):
    pred_params = {
        'unet': params['unet'],
        'text_encoder': freezed_params['text_encoder'],
        'vae': freezed_params['vae'],
        'scheduler': freezed_params['scheduler']
    }

    return pipeline._generate(
        prompt_ids=batch['input_ids'],
        params=pred_params,
        prng_seed=pred_rng,
        num_inference_steps=n_infer_steps,
        height=resolution,
        width=resolution)


def text_to_image_default_output_fn(batch_preds, numpy_to_pil_fn):
    return numpy_to_pil_fn(np.asarray(batch_preds))

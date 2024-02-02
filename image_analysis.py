import matplotlib.pyplot as plt
import numpy as np
import random
import torch
from torch.utils.data import DataLoader
from torchvision import transforms, models
from torchvision.datasets import ImageFolder


def load_dataset(transform, limit=1000, shuffle=True):
    """
    Load Stanford Dogs dataset and preprocess the images with a specified limit
    http://vision.stanford.edu/aditya86/ImageNetDogs/
    """
    dataset = ImageFolder('images_dataset', transform=transform)
    if shuffle:
        sample_list_index = random.sample(range(len(dataset)), limit)
        dataset = torch.utils.data.Subset(dataset, sample_list_index)
    else:
        dataset = torch.utils.data.Subset(dataset, range(limit))

    return dataset


def load_pre_trained_model(select_device):
    """
        Load the pre-trained model
    """
    model_set = models.resnet18(weights='IMAGENET1K_V1')

    # Set the model to evaluation mode to avoid updating the running statistics of batch normalization layers
    model_set.eval()

    # Freeze the parameters
    for param in model_set.parameters():
        param.requires_grad = False

    # Remove the classification (fully connected) layer
    model_set = torch.nn.Sequential(*(list(model_set.children())[:-1]))

    # set processing device
    model_set.to(select_device)

    return model_set


def calculate_similarity(features_of_all_images):
    """
    Calculate the similarity scores between images based on the inverse Euclidean distance of their features.
    """
    similarity_scores_list = []
    for i in range(len(features_of_all_images)):
        scores = []
        for j in range(len(features_of_all_images)):
            distance = np.linalg.norm(features_of_all_images[i] - features_of_all_images[j])
            if distance == 0:
                score = 1
            else:
                score = 1 / distance
            scores.append((j, score))
        similarity_scores_list.append(scores)
    return similarity_scores_list


def rank_normalization(similarity_lists):
    """
    Rank normalization of the similarity scores
    :param similarity_lists:
    :return:
    """

    normalized_similarity_scores = []
    L = len(similarity_lists[0])  # Length of each similarity list

    for i in range(len(similarity_lists)):
        ranks = []
        for j in range(len(similarity_lists[i])):
            rank = 2 * L - (similarity_lists[i][j][1] + similarity_lists[j][i][1])
            ranks.append((j, rank))  # Append a tuple instead of a list
        # append the sorted ranks, based on the rank (the second value of the tuple) to the normalized_similarity_scores list
        normalized_similarity_scores.append(sorted(ranks, key=lambda x: x[1]))

    return normalized_similarity_scores


def get_the_features_of_the_image(image, model):
    image_tensor = transform_pipeline(image)
    features_var = model(image_tensor.unsqueeze(0).to(device))  # extract features
    features = features_var.data.cpu()  # get the tensor out of the variable and copy it to host memory

    # print("Features of the image: ", features.size())

    return features


if __name__ == "__main__":
    print("Image Analysis: Final Exam")

    transform_pipeline = transforms.Compose([
        transforms.ToTensor()
    ])

    # Set the processing device
    device = 'cuda' if torch.cuda.is_available() else 'cpu'

    # Load the Stanford Dogs dataset
    data_loader = load_dataset(transform_pipeline)

    # Load the pre-trained model
    pre_trained_model = load_pre_trained_model(device)
    # print(pre_trained_model)

    # Get the first image from the dataset
    first_image, _ = next(iter(data_loader))

    # Convert the image tensor to a numpy array
    first_image = first_image.squeeze().permute(1, 2, 0).numpy()

    # Display the first image
    plt.imshow(first_image)
    plt.axis('off')
    plt.show()

    # Get all the features of the images
    features = []
    for image, _ in data_loader:
        # Add batch dimension to image tensor
        image = image.unsqueeze(0)

        # Move the image tensor to the same device as the pre-trained model
        image = image.to(device)

        # Pass the image through the ResNet18 model
        with torch.no_grad():
            feature = pre_trained_model(image).squeeze().cpu().numpy()  # Convert feature to numpy array

        # Append the feature vector to the list of features
        features.append(feature)

    # Make them 1D
    for i in range(len(features)):
        features[i] = features[i].reshape(features[i].size)


    # Calculate the Euclidean distance between the features of an image and the features of all images and store the
    # similarity scores
    similarity_scores = calculate_similarity(features)

    print(similarity_scores[0])
    print("Length of the euclidean distances: ", len(similarity_scores))

    # Rank normalization of the similarity scores
    normalized_similarity_scores = rank_normalization(similarity_scores)
    print(normalized_similarity_scores[0])

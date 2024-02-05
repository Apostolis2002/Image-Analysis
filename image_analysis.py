import math
import matplotlib.pyplot as plt
import numpy as np
import random
import torch
from torch.utils.data import DataLoader
from torchvision import transforms, models
from torchvision.datasets import ImageFolder
import os


def load_dataset(transform, limit=600, shuffle=True):
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
    model_set = models.resnet50(weights='IMAGENET1K_V1')

    # Set the model to evaluation mode to avoid updating the running statistics of batch normalization layers
    model_set.eval()

    # Remove the classification (fully connected) layer
    model_set = torch.nn.Sequential(*(list(model_set.children())[:-1]))

    # set processing device
    model_set.to(select_device)

    return model_set


def calculate_features(dataset_images):
    """
    Calculate the features of the images using the pre-trained model
    """
    features_list = []
    for ds_image, _ in dataset_images:
        # Add batch dimension to image tensor
        ds_image = ds_image.unsqueeze(0)

        # Move the image tensor to the same device as the pre-trained model
        ds_image = ds_image.to(device)

        # Pass the image through the ResNet18 model
        with torch.no_grad():
            feature = pre_trained_model(ds_image).squeeze().cpu().numpy()  # Convert feature to numpy array

        # Append the feature vector to the list of features
        features_list.append(feature)

    # Make them 1D
    for i in range(len(features_list)):
        features_list[i] = features_list[i].reshape(features_list[i].size)

    return features_list


def calculate_similarity(features_of_all_images):
    """
    Calculate the similarity scores between images based on the inverse Euclidean distance of their features.
    Similarity score = 1 / (Euclidean distance)
    """
    features_of_all_images = np.array(features_of_all_images)
    similarity_scores_list = []

    for i in range(len(features_of_all_images)):
        distances = np.linalg.norm(features_of_all_images - features_of_all_images[i], axis=1)
        scores = 1 / np.where(distances == 0, 0.00001, distances)  # Avoid division by zero
        similarity_scores_list.append(list(enumerate(scores)))

    return similarity_scores_list


def rank_normalization(similarity_lists):
    """
    ---Rank Normalization---

    Use similarity scores to sort
    """
    normalized_similarity_scores = []
    L = len(similarity_lists[0])  # Length of each similarity list

    for i in range(len(similarity_lists)):
        ranks = []
        for j in range(len(similarity_lists[i])):
            rank = 2 * L - (similarity_lists[i][j][1] + similarity_lists[j][i][1])
            ranks.append((j, rank))
        # sort the ranks based on the rank (the second value of the tuple) and append to the
        # normalized_similarity_scores list
        normalized_similarity_scores.append(sorted(ranks, key=lambda x: x[1]))

    return normalized_similarity_scores


def get_the_features_of_the_image(image, model):
    """
    ---Feature Extraction---

    Get the features of the image
    """
    image_tensor = transform_pipeline(image)
    features_var = model(image_tensor.unsqueeze(0).to(device))  # extract features
    features = features_var.data.cpu()  # get the tensor out of the variable and copy it to host memory

    return features


def get_hypergraph_construction(similarity_scores, k=5):
    """
    ---Hypergraph Construction---

    Create hyperedges as lists
    """
    hyperedges = []
    for i in range(len(similarity_scores)):
        hyperedge = []
        for j in range(k):
            hyperedge.append(similarity_scores[i][j][0])
        # Add the hyperedge to the hyperedges
        hyperedges.append(hyperedge)
    return hyperedges


def create_edge_associations(hyperedges, k=5):
    """
    ---Create Edge Associations---

    Create edge associations based on the hyperedges
    """
    associations = np.zeros((len(hyperedges), len(hyperedges)))
    for i, e in enumerate(hyperedges):
        for j in range(len(hyperedges)):
            if j in e:
                position = e.index(j) + 1  # Get the position of the node in the hyperedge
                associations[i][j] = 1 - math.log(position, k + 1)  # Calculate the weight
            else:
                associations[i][j] = 0
    return associations


def create_edge_weights(hyperedges, edge_associations):
    """
    ---Hyperedge Weight---

    Calculate the weights of the hyperedges
    """
    weights = []
    for i, e in enumerate(hyperedges):
        sum = 0
        for h in e:
            sum += edge_associations[i][h]
        weights.append(sum)
    return weights


def get_hyperedges_similarities(incidence_matrix):
    """
    ---Hyperedges Similarities---

    Compute the Hadamard product of the pairwise similary matrix
    """
    Similarity_matrix_h = incidence_matrix @ incidence_matrix.T  # Matrix multiplication
    Similarity_matrix_u = incidence_matrix.T @ incidence_matrix  # Matrix multiplication
    Similarity_matrix = np.multiply(Similarity_matrix_h, Similarity_matrix_u)  # Hadamard product
    return Similarity_matrix


def get_cartesian_product_of_hyperedge_elements(edge_weights, edge_associations, hyperedges):
    """
    ---Cartesian Product of Hyperedge Elements---

    Calculate cartesian product of the hyperedge elements.
    Then calculate the membership degrees of the hyperedges based on weights.
    Finally, calculate the matrix C.
    """
    membership_degrees = [{} for _ in range(len(hyperedges))]
    matrix_c = np.zeros((len(hyperedges), len(hyperedges)))
    for i, e in enumerate(hyperedges):
        eq_ei = np.transpose(np.meshgrid(e, e)).reshape(-1, 2)
        for (vertices1, vertices2) in eq_ei:
            membership_degrees[i][(vertices1, vertices2)] = edge_weights[i] * edge_associations[i][vertices1] * \
                                                            edge_associations[i][vertices2]
            matrix_c[vertices1][vertices2] += membership_degrees[i][(vertices1, vertices2)]
    return matrix_c


def get_hypergrapgh_based_simalarity(matrix_c, hyperedges_similarities):
    """
    ---Hypergraph-based similarity---

    Computes final affinity matrix.
    """
    affinity_matrix = np.multiply(matrix_c, hyperedges_similarities)
    return affinity_matrix


def show_image(image_index, save_image=False, image_name=""):
    image, _ = data_loader[image_index]
    image = image.squeeze().permute(1, 2, 0).numpy()
    plt.imshow(image)
    plt.axis('off')
    if not os.path.exists("retrieved_images"):
        os.makedirs("retrieved_images")
    if save_image and image_name != "":
        plt.savefig("retrieved_images/" + image_name + ".png")
    elif save_image:
        plt.savefig("retrieved_images/" + str(image_index) + ".png")
    plt.show()


def calculate_accuracy(retrieved_images, query_image_label):
    """
    Calculate the accuracy of the retrieved images
    """
    count = 0
    for i in range(len(retrieved_images)):
        image_index, score = retrieved_images[i]
        image, label = data_loader[image_index]
        print("Image index: {:<5} | Image label: {:<5} | Score: {:.6f}".format(image_index, label, score))
        if label == query_image_label:
            count += 1

    return (count / len(retrieved_images)) * 100


if __name__ == "__main__":
    print("Image Analysis: Final Exam")

    transform_pipeline = transforms.Compose([
        transforms.ToTensor()
    ])

    # Set the processing device
    device = 'cuda' if torch.cuda.is_available() else 'cpu'

    print("Device: ", device)

    # Load the Stanford Dogs dataset
    data_loader = load_dataset(transform_pipeline)

    print("Dataset size: ", len(data_loader))

    # Load the pre-trained model
    pre_trained_model = load_pre_trained_model(device)

    # print("Pre-trained model: ", pre_trained_model)

    # Get the first image from the dataset
    show_image(0)

    # Get all the features of the images
    features = calculate_features(data_loader)

    print("Extracted features: ", len(features), " features.")

    # ---LHRR Alogrithm---

    # Calculate the Euclidean distance between the features of an image and the features of all images and store the
    # similarity scores
    similarity_scores = calculate_similarity(features)

    print("Similarity scores calculated.")

    number_of_iterations = 9  # The number of iterations

    print("Number of iterations: ", number_of_iterations)

    for i in range(number_of_iterations):

        print("-----------Iteration: ", i + 1, "------------")

        # ---Rank Normalization---
        # Rank normalization of the similarity scores
        normalized_similarity_scores = rank_normalization(similarity_scores)

        print("Rank normalization completed.")

        # ---Hypergraph Construction---
        # Get the Hyperedges
        hyperedges = get_hypergraph_construction(normalized_similarity_scores)

        print("Hypergraph construction completed.")

        # Get the Edge Associations
        edge_associations = create_edge_associations(hyperedges)

        print("Edge associations created.")

        # Get the Edge Weights
        edge_weights = create_edge_weights(hyperedges, edge_associations)

        print("Edge weights created.")

        # ---Hyperedges Similarities---
        # Get the Hyperedges Similarities
        hyperedges_similarities = get_hyperedges_similarities(edge_associations)

        print("Hyperedges similarities calculated.")

        # ---Cartesian Product of Hyperedge Elements---
        # Get the Cartesian Product of Hyperedge Elements
        matrix_c = get_cartesian_product_of_hyperedge_elements(edge_weights, edge_associations, hyperedges)

        print("Cartesian product of hyperedge elements completed.")

        # ---Hypergraph-based similarity---
        # Get the Affinity Matrix
        affinity_matrix = get_hypergrapgh_based_simalarity(matrix_c, hyperedges_similarities)

        print("Affinity matrix calculated.")

        # Convert the affinity matrix to a list
        affinity_matrix_list = affinity_matrix.tolist()

        for h, row in enumerate(affinity_matrix_list):
            for j, v in enumerate(row):
                affinity_matrix_list[h][j] = (j, affinity_matrix_list[h][j])

        similarity_scores = affinity_matrix_list

        print("Similarity scores updated.")
        print("------Iteration: ", i + 1, " completed.------")

    # Retrieve the images
    query_image_index = 0
    retrieved_images = []
    for (i, score) in similarity_scores[query_image_index]:
        if score != 0:
            retrieved_images.append((i, score))
    retrieved_images = sorted(retrieved_images, key=lambda x: x[1], reverse=True)

    print("Retrieved images: ", len(retrieved_images))

    # Show the first 5 images
    retrieved_images = retrieved_images[:5]
    for i in range(len(retrieved_images)):
        image_index, score = retrieved_images[i]
        show_image(image_index, True, str(i))

    print("The top 5 retrieved images saved to the retrieved_images folder.")

    # Retrieved images accuracy: the class of the query image is the same as the class of the retrieved images
    query_image_label = data_loader[query_image_index][1]

    # Calculate the accuracy
    accuracy = calculate_accuracy(retrieved_images, query_image_label)
    print(f"Accuracy: {accuracy}%")
